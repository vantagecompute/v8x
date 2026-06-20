# Copyright (C) 2025 Vantage Compute Corporation
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
#!/usr/bin/env python3
# Copyright (c) 2025 Vantage Compute Corporation
# See LICENSE file for licensing details.
"""Vantage System on LXD deployment app for v8x."""

import logging
import os
import subprocess
import urllib.parse
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
from rich.text import Text
from vantage_sdk.cloud.crud import cloud_sdk
from vantage_sdk.cluster.schema import Cluster, VantageClusterContext

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.constants import V8X_LOCAL_USER_BASE_DIR
from v8x.deployment_apps.common import (
    create_deployment_with_init_status,
    generate_dev_cluster_data,
)
from v8x.deployments.crud import deployment_sdk
from v8x.deployments.schema import Deployment
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from .constants import APP_NAME, CLOUD, KEYCLOAK_TOKEN_PATH, SUBSTRATE, VANTAGE_PROVIDER_BINARY_URL
from .render import success_create_message, success_destroy_message

logger = logging.getLogger("v8x.apps.lxd.slurm")


# Environment variable names for LXD provider configuration
ENV_REGISTRY_URL = "VANTAGE_LXD_PROVIDER_REGISTRY_URL"
ENV_VANTAGE_API_URL = "VANTAGE_LXD_PROVIDER_VANTAGE_API_URL"
ENV_DEV_ARG = "VANTAGE_LXD_PROVIDER_DEV_ARG"


def _get_env_bool(env_var: str, default: bool) -> bool:
    """Get a boolean value from environment variable.

    Args:
        env_var: Name of the environment variable
        default: Default value if env var is not set

    Returns:
        Boolean value from env var or default
    """
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_env_str(env_var: str, default: Optional[str] = None) -> Optional[str]:
    """Get a string value from environment variable.

    Args:
        env_var: Name of the environment variable
        default: Default value if env var is not set

    Returns:
        String value from env var or default
    """
    return os.getenv(env_var, default) or default


def _get_keycloak_token(
    oidc_base_url: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Get a JWT token from Keycloak using client credentials.

    Args:
        oidc_base_url: Base URL for the OIDC provider
        client_id: Client ID for authentication
        client_secret: Client secret for authentication

    Returns:
        JWT access token string

    Raises:
        Exception: If token retrieval fails
    """
    token_url = f"{oidc_base_url}{KEYCLOAK_TOKEN_PATH}"
    logger.debug(f"Getting JWT token from {token_url}")

    with httpx.Client() as client:
        response = client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data["access_token"]


def _get_vantage_provider_binary_path() -> Path:
    """Get the path to the vantage-provider binary in ~/.vdeployer/.

    Returns:
        Path to the vantage-provider binary
    """
    return V8X_LOCAL_USER_BASE_DIR / "bin" / "vantage-provider"


def _download_vantage_provider_binary(
    vantage_cluster_ctx: VantageClusterContext,
) -> Path:
    """Download the vantage-provider binary with Keycloak authentication if not already present.

    The binary is stored in ~/.vdeployer/vantage-provider and will be reused if it already exists.

    Args:
        vantage_cluster_ctx: Context containing cluster credentials

    Returns:
        Path to the vantage-provider binary

    Raises:
        Exception: If download fails
    """
    binary_path = _get_vantage_provider_binary_path()

    # Check if binary already exists
    if binary_path.exists():
        logger.info(f"vantage-provider binary already exists at {binary_path}, skipping download")
        return binary_path
    else:
        binary_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading vantage-provider binary...")

    # Get JWT token for authenticated download
    token = _get_keycloak_token(
        oidc_base_url=vantage_cluster_ctx.oidc_base_url,
        client_id=vantage_cluster_ctx.client_id,
        client_secret=vantage_cluster_ctx.client_secret,
    )

    # Download the binary with authentication
    with httpx.Client() as client:
        response = client.get(
            VANTAGE_PROVIDER_BINARY_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        # Write the binary
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_bytes(response.content)
        binary_path.chmod(0o755)

    logger.info(f"vantage-provider binary installed to {binary_path}")
    return binary_path


def _run_vantage_provider_provision(  # noqa: C901
    ctx: typer.Context,
    vantage_cluster_ctx: VantageClusterContext,
    binary_path: Path,
) -> None:
    """Run vantage-provider provision command.

    Args:
        ctx: Typer context for console output
        vantage_cluster_ctx: Context containing cluster credentials and URLs
        binary_path: Path to the vantage-provider binary

    Raises:
        Exception: If provision command fails
    """
    console = ctx.obj.console

    # Build the vantage URL from oidc_base_url
    vantage_url = ctx.obj.settings.vantage_url

    lxd_server_addr = urllib.parse.urlparse(
        ctx.obj.cloud_config_metadata["lxd_server_url"]
    ).hostname
    lxd_server_port = urllib.parse.urlparse(ctx.obj.cloud_config_metadata["lxd_server_url"]).port
    lxd_client_cert = ctx.obj.cloud_config_metadata["lxd_client_cert"]
    lxd_client_key = ctx.obj.cloud_config_metadata["lxd_client_key"]

    # Use pre-generated client cert/key from CloudConfig (registered during cloud create)
    cmd = [
        str(binary_path),
        "lxd",
        "provision",
        "--vdeployer-web-chart-version",
        vantage_cluster_ctx.settings.get("vdeployer_web_chart_version", "latest"),
        "--vdeployer-istio-base-chart-version",
        vantage_cluster_ctx.settings.get("vdeployer_istio_base_chart_version", "latest"),
        "--cluster-client-id",
        vantage_cluster_ctx.client_id,
        "--cluster-client-secret",
        vantage_cluster_ctx.client_secret,
        "--vantage-url",
        vantage_url,
        "--remote-address",
        lxd_server_addr,
        "--remote-port",
        str(lxd_server_port),
        "--lxd-client-cert",
        lxd_client_cert,
        "--lxd-client-key",
        lxd_client_key,
        "--network",
        vantage_cluster_ctx.settings["autoscaler_lxd_default_network"],
        "--project",
        vantage_cluster_ctx.settings["lxd_project_name"],
    ]

    if default_storage_pool := vantage_cluster_ctx.settings.get(
        "autoscaler_lxd_default_storage_pool"
    ):
        cmd.extend(["--default-storage-pool", default_storage_pool])

    # Get control plane instance type from settings (from default_control_node_groups)
    control_node_groups = vantage_cluster_ctx.settings.get("default_control_node_groups", [])
    if control_node_groups:
        cp_instance_type = control_node_groups[0].get("instance_type", "control-plane-md")
        cmd.extend(["--control-plane-instance-type", cp_instance_type])

    if lxd_cluster_group := vantage_cluster_ctx.settings.get("lxd_cluster_group"):
        cmd.extend(["--cluster-group", lxd_cluster_group])

    # Optional second NIC (eth1) for direct VM access to Ceph storage network
    if second_net_parent := vantage_cluster_ctx.settings.get(
        "autoscaler_lxd_second_network_parent"
    ):
        cmd.extend(["--second-network-parent", second_net_parent])
    if second_net_nictype := vantage_cluster_ctx.settings.get(
        "autoscaler_lxd_second_network_nictype"
    ):
        cmd.extend(["--second-network-nictype", second_net_nictype])
    if second_net_mtu := vantage_cluster_ctx.settings.get("autoscaler_lxd_second_network_mtu"):
        cmd.extend(["--second-network-mtu", str(second_net_mtu)])

    # Optional third NIC (eth2) — UPLINK VLAN carrier for MetalLB.  Every VM
    # gets this NIC so speakers can ARP-announce LB VIPs on 192.168.8.0/24
    # directly, no OVN LB forwards required.
    if third_net_parent := vantage_cluster_ctx.settings.get("autoscaler_lxd_third_network_parent"):
        cmd.extend(["--third-network-parent", third_net_parent])
    if third_net_nictype := vantage_cluster_ctx.settings.get(
        "autoscaler_lxd_third_network_nictype"
    ):
        cmd.extend(["--third-network-nictype", third_net_nictype])
    if third_net_mtu := vantage_cluster_ctx.settings.get("autoscaler_lxd_third_network_mtu"):
        cmd.extend(["--third-network-mtu", str(third_net_mtu)])

    if extra_sans := vantage_cluster_ctx.settings.get("extra_api_server_sans"):
        if isinstance(extra_sans, list):
            for san in extra_sans:
                cmd.extend(["--extra-api-san", san])
        elif isinstance(extra_sans, str) and extra_sans:
            cmd.extend(["--extra-api-san", extra_sans])

    # Organization info for gateway-level Istio auth policy
    if org_id := vantage_cluster_ctx.settings.get("keycloak_organization_id"):
        cmd.extend(["--organization-id", org_id])

    if org_name := vantage_cluster_ctx.settings.get("keycloak_organization_name"):
        cmd.extend(["--organization-name", org_name])

    if ctx.obj.cloud_config_metadata.get("dev_mode"):
        cmd.append("--dev")

    # Debug: show command (redacting secrets)
    debug_cmd = cmd.copy()
    for i, arg in enumerate(debug_cmd):
        if i > 0 and debug_cmd[i - 1] in [
            "--cluster-client-secret",
            "--lxd-client-cert",
            "--lxd-client-key",
        ]:
            debug_cmd[i] = "***REDACTED***"
    logger.info(f"Running: {' '.join(debug_cmd)}")
    console.print(f"[dim]Command: {' '.join(debug_cmd)}[/dim]")
    console.print("[bold blue]Running vantage-lxd provision...[/bold blue]")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        console.print(Text.from_ansi(result.stdout))
    if result.stderr:
        console.print(Text.from_ansi(result.stderr), style="yellow")

    if result.returncode != 0:
        raise Exception(f"vantage-lxd provision failed with code {result.returncode}")

    logger.info("vantage-lxd provision completed successfully")


class LXDApiClient:
    """HTTP client for LXD REST API."""

    def __init__(
        self,
        server_url: str,
        client_cert: str,
        client_key: str,
        project: str = "vantage-system",
    ):
        """Initialize LXD API client.

        Args:
            server_url: LXD server URL (e.g., https://192.168.0.55:8443)
            client_cert: Client certificate content (PEM)
            client_key: Client key content (PEM)
            project: LXD project name
        """
        self.server_url = server_url.rstrip("/")
        self.project = project
        self._cert_content = client_cert
        self._key_content = client_key
        self._cert_file: Optional[Path] = None
        self._key_file: Optional[Path] = None

    def __enter__(self) -> "LXDApiClient":
        """Set up temporary cert/key files for httpx."""
        import tempfile

        # Write cert and key to temp files
        cert_fd, cert_path = tempfile.mkstemp(suffix=".crt")
        key_fd, key_path = tempfile.mkstemp(suffix=".key")

        with os.fdopen(cert_fd, "w") as f:
            f.write(self._cert_content)
        with os.fdopen(key_fd, "w") as f:
            f.write(self._key_content)

        self._cert_file = Path(cert_path)
        self._key_file = Path(key_path)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up temporary cert/key files."""
        if self._cert_file and self._cert_file.exists():
            self._cert_file.unlink()
        if self._key_file and self._key_file.exists():
            self._key_file.unlink()

    def _get_client(self, timeout: float = 60.0) -> httpx.Client:
        """Create an httpx client with LXD authentication."""
        if not self._cert_file or not self._key_file:
            raise RuntimeError("LXDApiClient must be used as context manager")

        return httpx.Client(
            cert=(str(self._cert_file), str(self._key_file)),
            verify=False,  # LXD uses self-signed certificates
            timeout=timeout,
        )

    def exec_command(
        self,
        container: str,
        command: list[str],
        timeout: float = 120.0,
    ) -> tuple[int, str, str, str]:
        """Execute a command in an LXD container via the REST API.

        Args:
            container: Container/VM name
            command: Command and arguments to execute
            timeout: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr, debug_info)

        Raises:
            Exception: If command execution fails
        """
        with self._get_client(timeout=timeout) as client:
            # Start exec operation with record-output
            exec_url = f"{self.server_url}/1.0/instances/{container}/exec?project={self.project}"
            logger.debug(f"Exec URL: {exec_url}")
            logger.debug(f"Command: {command}")

            exec_response = client.post(
                exec_url,
                json={
                    "command": command,
                    "record-output": True,
                    "wait-for-websocket": False,
                    "interactive": False,
                },
            )
            exec_response.raise_for_status()
            exec_data = exec_response.json()
            logger.debug(f"Exec response: {exec_data}")

            # Get operation URL
            operation_id = exec_data.get("operation", "")
            if not operation_id:
                raise Exception(f"No operation returned from exec: {exec_data}")

            # Wait for operation to complete
            wait_url = f"{self.server_url}{operation_id}/wait?timeout={int(timeout)}"
            logger.debug(f"Wait URL: {wait_url}")
            wait_response = client.get(wait_url)
            wait_response.raise_for_status()
            wait_data = wait_response.json()
            logger.debug(
                f"Wait response type={wait_data.get('type')}, status={wait_data.get('status')}, status_code={wait_data.get('status_code')}"
            )

            metadata = wait_data.get("metadata", {})
            if metadata is None:
                raise Exception(f"No metadata in operation response: {wait_data}")

            # Log full metadata for debugging
            import json

            logger.debug(f"Full metadata: {json.dumps(metadata, indent=2, default=str)}")

            # Check operation status
            status = metadata.get("status", "")
            status_code = metadata.get("status_code", 0)
            logger.debug(f"Operation status: {status}, status_code: {status_code}")

            if status == "Failure":
                err = metadata.get("err", "Unknown error")
                raise Exception(f"LXD exec failed: {err}")

            # Get return code - LXD puts it in metadata.metadata.return for exec operations
            exec_metadata = metadata.get("metadata", {}) or {}
            return_code = exec_metadata.get("return", metadata.get("return", -1))
            logger.debug(f"Return code: {return_code}")

            # Get output log URLs from metadata.output (not metadata.metadata.output)
            output = metadata.get("output", {}) or {}
            stdout_url = output.get("1", "")  # fd 1 = stdout
            stderr_url = output.get("2", "")  # fd 2 = stderr
            logger.debug(f"Output URLs: stdout={stdout_url}, stderr={stderr_url}")

            stdout_content = ""
            stderr_content = ""

            if stdout_url:
                # Output logs need the project parameter too
                log_url = f"{self.server_url}{stdout_url}"
                if "?" not in log_url:
                    log_url += f"?project={self.project}"
                log_response = client.get(log_url)
                logger.debug(f"Stdout response status: {log_response.status_code}, url: {log_url}")
                if log_response.status_code == 200:
                    stdout_content = log_response.text
                else:
                    logger.debug(
                        f"Stdout fetch failed: {log_response.status_code} - {log_response.text[:200]}"
                    )
                logger.debug(
                    f"Stdout ({len(stdout_content)} bytes): {stdout_content[:200] if stdout_content else '(empty)'}"
                )

            if stderr_url:
                log_url = f"{self.server_url}{stderr_url}"
                if "?" not in log_url:
                    log_url += f"?project={self.project}"
                log_response = client.get(log_url)
                logger.debug(f"Stderr response status: {log_response.status_code}, url: {log_url}")
                if log_response.status_code == 200:
                    stderr_content = log_response.text
                else:
                    logger.debug(
                        f"Stderr fetch failed: {log_response.status_code} - {log_response.text[:200]}"
                    )
                logger.debug(
                    f"Stderr ({len(stderr_content)} bytes): {stderr_content[:200] if stderr_content else '(empty)'}"
                )

            debug_info = f"stdout_url={stdout_url or 'none'}, stderr_url={stderr_url or 'none'}"
            return return_code, stdout_content, stderr_content, debug_info

    def get_instance_state(self, container: str) -> dict:
        """Get the state of an LXD instance.

        Args:
            container: Container/VM name

        Returns:
            Instance state dictionary with status, processes, network, etc.
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/instances/{container}/state?project={self.project}"
            response = client.get(url)
            response.raise_for_status()
            return response.json().get("metadata", {})

    def is_agent_ready(self, container: str) -> bool:
        """Check if the LXD agent is ready in a VM.

        For VMs, the lxd-agent needs to be running inside before exec works.

        Args:
            container: Container/VM name

        Returns:
            True if agent is ready, False otherwise
        """
        try:
            state = self.get_instance_state(container)
            # For VMs, check if the status is "Running" and processes > 0
            status = state.get("status", "")
            processes = state.get("processes", 0)
            # Also check network - if agent is ready, we should see network info
            network = state.get("network", {})

            logger.debug(
                f"Instance state: status={status}, processes={processes}, network={bool(network)}"
            )

            return status == "Running" and processes > 0 and bool(network)
        except Exception as e:
            logger.debug(f"Error checking agent state: {e}")
            return False

    def get_instance_ip(self, container: str) -> Optional[str]:
        """Get the primary IP address of an LXD instance.

        Args:
            container: Container/VM name

        Returns:
            IP address string or None if not found
        """
        try:
            state = self.get_instance_state(container)
            network = state.get("network", {})

            # Look for eth0 or enp5s0 (common VM interface names)
            for iface_name in ["eth0", "enp5s0", "enp6s0"]:
                if iface_name in network:
                    addresses = network[iface_name].get("addresses", [])
                    for addr in addresses:
                        if addr.get("family") == "inet" and addr.get("scope") == "global":
                            return addr.get("address")

            # Fallback: check all interfaces for a global IPv4 address
            for iface_name, iface_data in network.items():
                if iface_name == "lo":
                    continue
                addresses = iface_data.get("addresses", [])
                for addr in addresses:
                    if addr.get("family") == "inet" and addr.get("scope") == "global":
                        return addr.get("address")

            return None
        except Exception as e:
            logger.debug(f"Error getting instance IP: {e}")
            return None

    def list_instances(self) -> list[str]:
        """List all instances in the project.

        Returns:
            List of instance names
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/instances?project={self.project}"
            response = client.get(url)
            response.raise_for_status()
            # Response is list of URLs like /1.0/instances/name
            instances = response.json().get("metadata", [])
            return [inst.split("/")[-1] for inst in instances]

    def delete_instance(self, name: str, force: bool = True) -> None:
        """Delete an instance.

        Args:
            name: Instance name
            force: Force delete (stop if running)
        """
        with self._get_client(timeout=120.0) as client:
            # First stop the instance if force is True
            if force:
                try:
                    stop_url = (
                        f"{self.server_url}/1.0/instances/{name}/state?project={self.project}"
                    )
                    stop_resp = client.put(stop_url, json={"action": "stop", "force": True})
                    if stop_resp.status_code == 202:
                        # Wait for stop operation
                        op_url = stop_resp.json().get("operation", "")
                        if op_url:
                            client.get(f"{self.server_url}{op_url}/wait?timeout=60")
                except Exception as e:
                    logger.debug(f"Error stopping instance {name}: {e}")

            # Delete the instance
            url = f"{self.server_url}/1.0/instances/{name}?project={self.project}"
            response = client.delete(url)
            response.raise_for_status()

            # Wait for delete operation
            op_url = response.json().get("operation", "")
            if op_url:
                client.get(f"{self.server_url}{op_url}/wait?timeout=120")

    def list_images(self) -> list[str]:
        """List all images in the project.

        Returns:
            List of image fingerprints
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/images?project={self.project}"
            response = client.get(url)
            response.raise_for_status()
            images = response.json().get("metadata", [])
            return [img.split("/")[-1] for img in images]

    def delete_image(self, fingerprint: str) -> None:
        """Delete an image.

        Args:
            fingerprint: Image fingerprint
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/images/{fingerprint}?project={self.project}"
            response = client.delete(url)
            response.raise_for_status()

            op_url = response.json().get("operation", "")
            if op_url:
                client.get(f"{self.server_url}{op_url}/wait?timeout=60")

    def list_profiles(self) -> list[str]:
        """List all profiles in the project.

        Returns:
            List of profile names
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/profiles?project={self.project}"
            response = client.get(url)
            response.raise_for_status()
            profiles = response.json().get("metadata", [])
            return [p.split("/")[-1] for p in profiles]

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Args:
            name: Profile name
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/profiles/{name}?project={self.project}"
            response = client.delete(url)
            response.raise_for_status()

    def list_storage_pools(self) -> list[str]:
        """List all storage pools.

        Returns:
            List of storage pool names
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/storage-pools"
            response = client.get(url)
            response.raise_for_status()
            pools = response.json().get("metadata", [])
            return [p.split("/")[-1] for p in pools]

    def list_storage_volumes(self, pool: str, volume_type: str = "custom") -> list[str]:
        """List storage volumes in a pool.

        Args:
            pool: Storage pool name
            volume_type: Volume type (custom, container, image, virtual-machine)

        Returns:
            List of volume names
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/storage-pools/{pool}/volumes/{volume_type}?project={self.project}"
            response = client.get(url)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            volumes = response.json().get("metadata", [])
            return [v.split("/")[-1] for v in volumes]

    def delete_storage_volume(self, pool: str, name: str, volume_type: str = "custom") -> None:
        """Delete a storage volume.

        Args:
            pool: Storage pool name
            name: Volume name
            volume_type: Volume type
        """
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/storage-pools/{pool}/volumes/{volume_type}/{name}?project={self.project}"
            response = client.delete(url)
            response.raise_for_status()

    def delete_project(self) -> None:
        """Delete the project."""
        with self._get_client() as client:
            url = f"{self.server_url}/1.0/projects/{self.project}"
            response = client.delete(url)
            response.raise_for_status()

    def project_exists(self) -> bool:
        """Check if the project exists.

        Returns:
            True if project exists, False otherwise
        """
        try:
            with self._get_client() as client:
                url = f"{self.server_url}/1.0/projects/{self.project}"
                response = client.get(url)
                return response.status_code == 200
        except Exception:
            return False

    def get_file(self, container: str, path: str) -> tuple[bool, str]:
        """Read a file from an LXD instance using the files API.

        Args:
            container: Container/VM name
            path: Path to the file inside the instance

        Returns:
            Tuple of (success, content_or_error)
        """
        try:
            with self._get_client() as client:
                url = f"{self.server_url}/1.0/instances/{container}/files?path={path}&project={self.project}"
                response = client.get(url)
                if response.status_code == 200:
                    return True, response.text
                elif response.status_code == 404:
                    return False, "File not found"
                else:
                    return False, f"HTTP {response.status_code}: {response.text[:100]}"
        except Exception as e:
            return False, str(e)

    def file_exists(self, container: str, path: str) -> bool:
        """Check if a file exists in an LXD instance.

        Args:
            container: Container/VM name
            path: Path to the file inside the instance

        Returns:
            True if file exists, False otherwise
        """
        success, _ = self.get_file(container, path)
        return success

    # vdeployer-web helpers live in deployment_apps.common.


async def _trigger_vdeployer_deploy(
    ctx: typer.Context,
    deployment: Deployment,
) -> None:
    """Trigger the vdeployer deploy via POST /deploy through the tunnel.

    Builds the settings payload from the cluster's creation_parameters and
    sends it to vdeployer-web. The deploy runs in the background on the
    vdeployer-web side.
    """
    import httpx
    from vantage_sdk.workbench._vdeployer import get_vdeployer_web_url

    from v8x.deployment_apps.common import get_auth_headers

    console = ctx.obj.console
    vctx = deployment.vantage_cluster_ctx

    vdeployer_url = get_vdeployer_web_url(
        client_id=vctx.client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )
    url = f"{vdeployer_url}/deploy"

    # Build settings from the cluster's stored creation_parameters.settings
    deploy_settings = dict(vctx.settings)
    deploy_settings["keycloak_client_id"] = vctx.client_id
    deploy_settings["keycloak_client_secret"] = vctx.client_secret
    deploy_settings["keycloak_organization_id"] = vctx.org_id
    deploy_settings["sssd_binder_password"] = vctx.sssd_binder_password
    deploy_settings["vantage_url"] = ctx.obj.settings.vantage_url
    if vctx.jupyterhub_token:
        deploy_settings["jupyterhub_service_token"] = vctx.jupyterhub_token

    try:
        headers = get_auth_headers(ctx)
    except Exception:
        from v8x.auth import fetch_auth_tokens, init_persona
        from v8x.cache import save_tokens_to_cache

        console.print("[yellow]⚠ Token expired before deploy, re-authenticating...[/yellow]")
        token_set = await fetch_auth_tokens(ctx.obj)
        save_tokens_to_cache(ctx.obj.profile, token_set)
        init_persona(ctx, token_set)
        headers = get_auth_headers(ctx)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={"settings": deploy_settings},
                headers=headers,
            )

        if response.status_code == 200:
            result = response.json()
            console.print(
                f"[green]\u2713[/green] {result.get('message', 'Deployment started in background')}"
            )
        elif response.status_code == 409:
            result = response.json()
            console.print(
                f"[yellow]Note:[/yellow] {result.get('detail', 'A deployment is already in progress')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to trigger deploy: {e}")
        raise


async def _deploy_vantage_system_lxd(
    ctx: typer.Context,
    deployment: Deployment,
) -> None:
    """Deploy Vantage System on LXD using the vantage-lxd binary.

    Args:
        ctx: Typer context containing CLI configuration
        deployment: Deployment object with metadata and configuration

    Raises:
        Exception: If deployment fails
    """
    console = ctx.obj.console

    # Step 1: Download the vantage-provider binary (or use existing one)
    console.print("[bold blue]Step 1: Downloading vantage-provider binary...[/bold blue]")
    binary_path = _download_vantage_provider_binary(deployment.vantage_cluster_ctx)
    console.print("[green]✓[/green] vantage-provider binary ready")

    # Step 2: Run vantage-provider provision
    console.print("")
    console.print("[bold blue]Step 2: Running vantage-provider provision...[/bold blue]")
    _run_vantage_provider_provision(
        ctx=ctx,
        vantage_cluster_ctx=deployment.vantage_cluster_ctx,
        binary_path=binary_path,
    )
    console.print("[green]✓[/green] vantage-provider provision completed")

    # Step 3: Wait for vdeployer-web to be ready via tunnel
    console.print("")
    console.print("[bold blue]Step 3: Waiting for vdeployer-web...[/bold blue]")
    from v8x.deployment_apps.common import wait_for_vdeployer_web_ready

    await wait_for_vdeployer_web_ready(
        ctx=ctx,
        client_id=deployment.vantage_cluster_ctx.client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )

    # Step 4: Trigger vdeployer deploy via POST /deploy
    # This is needed because on --resume the markClusterReady mutation
    # (which normally triggers the deploy) may not re-fire.
    console.print("")
    console.print("[bold blue]Step 4: Triggering vdeployer deploy...[/bold blue]")
    await _trigger_vdeployer_deploy(ctx=ctx, deployment=deployment)


async def create(
    ctx: typer.Context,
    cluster: Cluster,
) -> typer.Exit:
    """Create Vantage System on LXD cluster using cluster data.

    LXD-specific configuration is retrieved from ctx.obj.cloud_config_metadata,
    which is populated from the CloudConfig created with 'v8x cloud create'.

    Args:
        ctx: Typer context containing CLI configuration and cloud_config_metadata
        cluster: Cluster object with configuration and client credentials

    Raises:
        typer.Exit: If deployment fails due to missing or invalid cluster data
    """
    verbose = ctx.obj.verbose
    settings = ctx.obj.settings
    console = ctx.obj.console

    # Get LXD-specific metadata from CloudConfig (set by cluster create command)
    cloud_config_metadata = getattr(ctx.obj, "cloud_config_metadata", {}) or {}

    # Verify LXD client certificate and key exist (should have been created with CloudConfig)
    if not cloud_config_metadata.get("lxd_client_cert") or not cloud_config_metadata.get(
        "lxd_client_key"
    ):
        console.print(
            "[bold red]Error:[/bold red] LXD client certificate not found in CloudConfig.\n"
            "This should have been generated when the CloudConfig was created.\n"
            "Please recreate the CloudConfig with: v8x cloud delete <name> && v8x cloud create ..."
        )
        return typer.Exit(code=1)

    org_id = ctx.obj.persona.identity_data.org_id

    client_secret = cluster.client_secret
    sssd_binder_password = cluster.sssd_binder_password

    if sssd_binder_password is None:
        console.print(
            "[bold red]Error:[/bold red] Cluster is missing SSSD binder password. Please debug"
        )
        return typer.Exit(code=1)

    if client_secret is None:
        console.print("[bold red]Error:[/bold red] Cluster is missing client secret. Please debug")
        return typer.Exit(code=1)

    vantage_cluster_ctx = VantageClusterContext(
        cluster_name=cluster.name,
        client_id=cluster.client_id,
        client_secret=client_secret,
        base_api_url=settings.get_apis_url(),
        oidc_base_url=settings.get_auth_url(),
        oidc_domain=settings.oidc_domain,
        tunnel_api_url=settings.get_tunnel_url(),
        jupyterhub_token=cluster.creation_parameters["jupyterhub_token"],
        sssd_binder_password=sssd_binder_password,
        ldap_url=settings.get_ldap_url(),
        org_id=org_id,
        settings=cluster.creation_parameters["settings"],
    )

    # Get the LXD cloud configuration
    cloud = cloud_sdk.get(CLOUD)
    if cloud is None:
        console.print(f"[bold red]Error:[/bold red] Cloud '{CLOUD}' not found. Please debug")
        return typer.Exit(code=1)

    deployment = create_deployment_with_init_status(
        app_name=APP_NAME,
        cluster=cluster,
        vantage_cluster_ctx=vantage_cluster_ctx,
        verbose=verbose,
        cloud=cloud,
        cloud_account_id=None,
        substrate=SUBSTRATE,
        additional_metadata=cloud_config_metadata,
    )
    deployment.write()

    try:
        await _deploy_vantage_system_lxd(ctx=ctx, deployment=deployment)
    except Exception as e:
        deployment.status = "error"
        deployment.write()
        ctx.obj.console.print(f"[bold red]Error:[/bold red] Deployment failed: {e}")
        return typer.Exit(code=1)

    deployment.status = "active"
    deployment.write()

    vantage_url = vantage_cluster_ctx.oidc_base_url.replace("auth.", "app.")
    ctx.obj.console.print(success_create_message(deployment=deployment, vantage_url=vantage_url))
    return typer.Exit(0)


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_command(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Argument(help="Name of the cluster to deploy"),
    ],
    dev_mode: Annotated[
        bool,
        typer.Option("--dev", help="Enable development mode"),
    ] = False,
    dev_run: Annotated[
        bool,
        typer.Option("--dev-run", help="Use dummy cluster data for local development"),
    ] = False,
) -> Optional[typer.Exit]:
    """Create a Vantage System on LXD and register it with Vantage."""
    cluster = generate_dev_cluster_data(cluster_name)

    if not dev_run:
        from vantage_sdk.cluster.crud import cluster_sdk

        cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
        if cluster is None:
            return typer.Exit(code=1)
        # sssd_binder_password is now fetched automatically by get_cluster_by_name
        if cluster.sssd_binder_password is None:
            ctx.obj.console.print(
                "[bold red]Error:[/bold red] Could not retrieve SSSD binder password from organization settings."
            )
            return typer.Exit(code=1)

    # Populate cloud_config_metadata in context for the create() function
    ctx.obj.cloud_config_metadata = {
        "dev_mode": dev_mode,
    }

    await create(
        ctx=ctx,
        cluster=cluster,
    )


async def _remove_vantage_system_lxd(  # noqa: C901
    ctx: typer.Context, deployment: Deployment
) -> None:
    """Remove a Vantage System on LXD deployment.

    Uses vantage-lxd binary if credentials are available, otherwise falls back
    to LXD REST API.

    Args:
        ctx: Typer context containing console object
        deployment: Deployment object containing deployment information

    Raises:
        Exception: If cleanup fails
    """
    console = ctx.obj.console
    settings = ctx.obj.settings
    project_name = "vantage-system"

    logger.info("Removing Vantage System on LXD deployment...")

    # Get LXD credentials from cloud config metadata
    cloud_config_metadata = getattr(ctx.obj, "cloud_config_metadata", {}) or {}
    lxd_server_url = cloud_config_metadata.get("lxd_server_url")
    lxd_client_cert = cloud_config_metadata.get("lxd_client_cert")
    lxd_client_key = cloud_config_metadata.get("lxd_client_key")

    # Try to use vantage-lxd binary if credentials are available
    if deployment.cluster.client_secret:
        try:
            vantage_cluster_ctx = VantageClusterContext(
                cluster_name=deployment.cluster.name,
                client_id=deployment.cluster.client_id,
                client_secret=deployment.cluster.client_secret,
                base_api_url=settings.get_apis_url(),
                oidc_base_url=settings.get_auth_url(),
                oidc_domain=settings.oidc_domain,
                tunnel_api_url=settings.get_tunnel_url(),
                jupyterhub_token="",
                sssd_binder_password="",
                ldap_url=settings.get_ldap_url(),
                org_id=ctx.obj.persona.identity_data.org_id,
            )

            console.print("[bold blue]Downloading vantage-provider binary...[/bold blue]")
            binary_path = _download_vantage_provider_binary(vantage_cluster_ctx)
            console.print("[green]✓[/green] vantage-provider binary ready")

            console.print("[bold blue]Running lxd delete...[/bold blue]")

            # Build command with LXD credentials for remote server
            cmd = [str(binary_path), "lxd", "delete", "--force"]
            if lxd_server_url:
                lxd_addr = urllib.parse.urlparse(lxd_server_url).hostname
                lxd_port = urllib.parse.urlparse(lxd_server_url).port
                cmd.extend(["--remote-address", lxd_addr])
                if lxd_port:
                    cmd.extend(["--remote-port", str(lxd_port)])
            if lxd_client_cert:
                cmd.extend(["--lxd-client-cert", lxd_client_cert])
            if lxd_client_key:
                cmd.extend(["--lxd-client-key", lxd_client_key])

            # Debug: show command (redacting secrets)
            debug_cmd = cmd.copy()
            for i, arg in enumerate(debug_cmd):
                if i > 0 and debug_cmd[i - 1] in ["--lxd-client-cert", "--lxd-client-key"]:
                    debug_cmd[i] = "***REDACTED***"
            logger.info(f"Running: {' '.join(debug_cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.stdout:
                console.print(Text.from_ansi(result.stdout))
            if result.stderr:
                console.print(Text.from_ansi(result.stderr), style="yellow")

            if result.returncode == 0:
                logger.info("vantage-lxd delete completed successfully")
                return
            else:
                logger.warning(
                    f"vantage-lxd delete failed with code {result.returncode}, falling back to LXD API"
                )
        except Exception as e:
            logger.warning(f"Failed to use vantage-lxd binary: {e}, falling back to LXD API")

    # Fallback: Use LXD REST API
    if not lxd_server_url or not lxd_client_cert or not lxd_client_key:
        raise Exception(
            "Cannot remove LXD project: LXD credentials not found in cloud config. "
            "Please ensure the cloud config has lxd_server_url, lxd_client_cert, and lxd_client_key."
        )

    console.print("[bold blue]Removing LXD project using LXD REST API...[/bold blue]")

    with LXDApiClient(
        server_url=lxd_server_url,
        client_cert=lxd_client_cert,
        client_key=lxd_client_key,
        project=project_name,
    ) as lxd_client:
        # Check if project exists
        if not lxd_client.project_exists():
            console.print(
                f"[yellow]Project '{project_name}' does not exist, nothing to remove[/yellow]"
            )
            return

        # First, stop and delete all instances in the project
        console.print(f"[dim]Stopping and deleting instances in project '{project_name}'...[/dim]")
        try:
            instances = lxd_client.list_instances()
            for instance in instances:
                console.print(f"[dim]  Deleting instance '{instance}'...[/dim]")
                try:
                    lxd_client.delete_instance(instance, force=True)
                except Exception as e:
                    logger.warning(f"Failed to delete instance {instance}: {e}")
        except Exception as e:
            logger.warning(f"Error listing/deleting instances: {e}")

        # Delete images in the project
        console.print(f"[dim]Cleaning up images in project '{project_name}'...[/dim]")
        try:
            images = lxd_client.list_images()
            for fingerprint in images:
                console.print(f"[dim]  Deleting image '{fingerprint[:12]}'...[/dim]")
                try:
                    lxd_client.delete_image(fingerprint)
                except Exception as e:
                    logger.warning(f"Failed to delete image {fingerprint[:12]}: {e}")
        except Exception as e:
            logger.warning(f"Error listing/deleting images: {e}")

        # Delete profiles (except 'default' which can't be deleted)
        console.print(f"[dim]Cleaning up profiles in project '{project_name}'...[/dim]")
        try:
            profiles = lxd_client.list_profiles()
            for profile in profiles:
                if profile != "default":
                    console.print(f"[dim]  Deleting profile '{profile}'...[/dim]")
                    try:
                        lxd_client.delete_profile(profile)
                    except Exception as e:
                        logger.warning(f"Failed to delete profile {profile}: {e}")
        except Exception as e:
            logger.warning(f"Error listing/deleting profiles: {e}")

        # Delete storage volumes
        console.print(f"[dim]Cleaning up storage volumes in project '{project_name}'...[/dim]")
        try:
            pools = lxd_client.list_storage_pools()
            for pool in pools:
                try:
                    volumes = lxd_client.list_storage_volumes(pool, "custom")
                    for vol_name in volumes:
                        console.print(
                            f"[dim]  Deleting storage volume '{vol_name}' from pool '{pool}'...[/dim]"
                        )
                        try:
                            lxd_client.delete_storage_volume(pool, vol_name, "custom")
                        except Exception as e:
                            logger.warning(f"Failed to delete volume {vol_name}: {e}")
                except Exception as e:
                    logger.debug(f"Error listing volumes in pool {pool}: {e}")
        except Exception as e:
            logger.warning(f"Error listing/deleting storage volumes: {e}")

        # Delete the project itself
        console.print(f"[dim]Deleting project '{project_name}'...[/dim]")
        try:
            lxd_client.delete_project()
        except Exception as e:
            raise Exception(f"Failed to delete LXD project: {e}")

    logger.info("LXD project deleted successfully via LXD REST API")
    console.print(f"[green]✓[/green] LXD project '{project_name}' deleted")


async def remove(ctx: typer.Context, deployment: Deployment) -> None:
    """Remove a Vantage System on LXD deployment.

    Args:
        ctx: The typer context object for console access.
        deployment: The deployment object to remove

    Raises:
        Exception: If removal fails (non-critical, logged and continued)
    """
    await _remove_deployment(ctx=ctx, deployment=deployment)


@handle_abort
@attach_settings
async def remove_command(
    ctx: typer.Context,
    deployment_id: Annotated[
        str,
        typer.Argument(help="ID of the deployment to remove"),
    ],
) -> None:
    """Remove a Vantage System on LXD deployment."""
    deployment = await deployment_sdk.get_deployment(ctx, deployment_id)
    if deployment is not None:
        await remove(ctx=ctx, deployment=deployment)
        await deployment_sdk.delete(deployment.id)
        ctx.obj.console.print(
            f"[green]✓[/green] Deployment '{deployment.name}' removed successfully"
        )
        return

    ctx.obj.console.print(f"[bold red]Error:[/bold red] Deployment '{deployment_id}' not found.")
    return


async def _remove_deployment(ctx: typer.Context, deployment: Deployment) -> None:
    """Remove a Vantage System on LXD deployment.

    Args:
        ctx: The typer context object for console access.
        deployment: The deployment object to remove

    Raises:
        Exception: If removal fails (non-critical, logged and continued)
    """
    try:
        await _remove_vantage_system_lxd(ctx, deployment)
    except Exception as e:
        logger.warning(f"Vantage System on LXD removal failed: {e}")
        raise
    ctx.obj.console.print(success_destroy_message(deployment=deployment))
