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
"""Deploy command for vdeployer-web."""

from pathlib import Path
from typing import Optional

import httpx
import typer
import yaml
from typing_extensions import Annotated
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


def get_vdeployer_web_url(client_id: str, vantage_url: str) -> str:
    """Construct the vdeployer-web base URL from client_id and vantage_url.

    Args:
        client_id: The cluster client ID
        vantage_url: The vantage URL (e.g., https://dev.vantagecompute.ai or https://app.dev.vantagecompute.ai)

    Returns:
        The vdeployer-web base URL
    """
    import urllib.parse

    # Extract domain from vantage_url (e.g., "https://app.dev.vantagecompute.ai" -> "dev.vantagecompute.ai")
    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    # Remove "app." prefix if present
    base_domain = hostname.removeprefix("app.")
    return f"https://{client_id}.clusters.{base_domain}/vdeployer"


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def deploy_command(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Name of the cluster to deploy to")],
    no_wan: Annotated[
        bool,
        typer.Option(
            "--no-wan",
            help="Bypass API calls and use settings from --settings-file instead",
        ),
    ] = False,
    settings_file: Annotated[
        Optional[Path],
        typer.Option(
            "--settings-file",
            help="Path to a YAML file containing vdeployer settings (required with --no-wan)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    client_id: Annotated[
        Optional[str],
        typer.Option(
            "--client-id",
            help="Cluster client ID (required with --no-wan, used for URL construction)",
        ),
    ] = None,
    client_secret: Annotated[
        Optional[str],
        typer.Option(
            "--client-secret",
            help="Keycloak client secret (required with --no-wan)",
        ),
    ] = None,
    sssd_password: Annotated[
        Optional[str],
        typer.Option(
            "--sssd-password",
            help="SSSD binder password (required with --no-wan)",
        ),
    ] = None,
    provider: Annotated[
        Optional[str],
        typer.Option(
            "--provider",
            help="Cloud provider (e.g., lxd, aws) - required with --no-wan",
        ),
    ] = None,
    org_id: Annotated[
        Optional[str],
        typer.Option(
            "--org-id",
            help="Organization ID for Keycloak (defaults to current profile org)",
        ),
    ] = None,
):
    r"""Trigger a deploy operation on a cluster via vdeployer-web.

    This command retrieves the cluster's settings from creationParameters
    and sends them to the vdeployer-web /deploy endpoint to trigger
    a deployment of Vantage K8S infrastructure components.

    Use --no-wan mode to bypass API calls and use local settings file instead.
    This is useful when the API is unavailable or for offline deployments.

    Examples:
        # Normal mode (fetches settings from API)
        v8x vdeployer-web deploy my-cluster

        # No-WAN mode (uses local settings file)
        v8x vdeployer-web deploy my-cluster --no-wan \
            --settings-file ./dev-settings/vdeployer-settings.yaml \
            --client-id my-cluster \
            --client-secret "secret123" \
            --sssd-password "password123" \
            --provider lxd
    """
    formatter = ctx.obj.formatter

    try:
        if no_wan:
            # No-WAN mode: use settings from file
            await _deploy_no_wan(
                ctx=ctx,
                cluster_name=cluster_name,
                settings_file=settings_file,
                client_id=client_id,
                client_secret=client_secret,
                sssd_password=sssd_password,
                provider=provider,
                org_id=org_id,
            )
        else:
            # Normal mode: fetch settings from API
            await _deploy_from_api(ctx=ctx, cluster_name=cluster_name)

    except Abort:
        raise
    except httpx.RequestError as e:
        raise Abort(
            f"Failed to connect to vdeployer-web: {e}",
            subject="Connection Error",
            log_message=f"httpx error: {e}",
        )
    except Exception as e:
        formatter.render_error(
            error_message=f"An unexpected error occurred: {e}",
            details={"error": str(e)},
        )


async def _deploy_no_wan(
    ctx: typer.Context,
    cluster_name: str,
    settings_file: Optional[Path],
    client_id: Optional[str],
    client_secret: Optional[str],
    sssd_password: Optional[str],
    provider: Optional[str],
    org_id: Optional[str],
):
    """Deploy using local settings file (no API calls)."""
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    # Validate required options for no-wan mode
    if not settings_file:
        raise Abort(
            "--settings-file is required when using --no-wan mode",
            subject="Missing Settings File",
            log_message="--no-wan requires --settings-file",
        )
    if not client_id:
        raise Abort(
            "--client-id is required when using --no-wan mode",
            subject="Missing Client ID",
            log_message="--no-wan requires --client-id",
        )
    if not client_secret:
        raise Abort(
            "--client-secret is required when using --no-wan mode",
            subject="Missing Client Secret",
            log_message="--no-wan requires --client-secret",
        )
    if not sssd_password:
        raise Abort(
            "--sssd-password is required when using --no-wan mode",
            subject="Missing SSSD Password",
            log_message="--no-wan requires --sssd-password",
        )
    if not provider:
        raise Abort(
            "--provider is required when using --no-wan mode",
            subject="Missing Provider",
            log_message="--no-wan requires --provider",
        )

    # Load settings from YAML file
    console.print(f"[dim]Loading settings from {settings_file}...[/dim]")
    try:
        with open(settings_file) as f:
            settings_dict = yaml.safe_load(f) or {}
        if not isinstance(settings_dict, dict):
            raise Abort(
                "Settings file must contain a YAML mapping (dict), not a list or scalar.",
                subject="Invalid Settings File Format",
                log_message=f"Invalid settings file format: {type(settings_dict).__name__}",
            )
    except yaml.YAMLError as e:
        raise Abort(
            f"Invalid YAML in --settings-file: {e}",
            subject="Invalid Settings YAML",
            log_message=f"YAML parse error: {e}",
        )

    # Add required fields
    settings_dict["provider"] = provider
    settings_dict["cluster_name"] = cluster_name
    settings_dict["keycloak_client_id"] = client_id
    settings_dict["keycloak_client_secret"] = client_secret
    settings_dict["sssd_binder_password"] = sssd_password

    # Use org_id from parameter or fall back to current profile
    keycloak_org_id = org_id or ctx.obj.persona.identity_data.org_id
    settings_dict["keycloak_organization_id"] = keycloak_org_id

    # Construct the vdeployer-web URL
    vdeployer_url = get_vdeployer_web_url(
        client_id=client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )
    deploy_url = f"{vdeployer_url}/deploy"

    console.print("[dim]Sending deploy request to vdeployer-web (no-wan mode)...[/dim]")
    console.print(f"[dim]URL: {deploy_url}[/dim]")

    # Make the POST request to /deploy (authenticated)
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(
            deploy_url,
            json={"settings": settings_dict},
            headers={"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"},
        )

    if response.status_code == 200:
        result = response.json()
        formatter.success(f"Deploy triggered successfully: {result.get('message', 'OK')}")

        # Build display data with settings flattened
        display_data = {
            "cluster": cluster_name,
            "client_id": client_id,
            "provider": provider,
            "vdeployer_url": vdeployer_url,
            "mode": "no-wan",
        }
        # Add each setting as a separate row with "settings." prefix
        for key, value in settings_dict.items():
            display_data[f"settings.{key}"] = value

        formatter.render_get(
            data=display_data,
            resource_name="Deploy Request",
        )
    elif response.status_code == 409:
        result = response.json()
        raise Abort(
            f"Deploy conflict: {result.get('detail', 'A task is already running')}",
            subject="Deploy Conflict",
            log_message=f"Deploy conflict: {response.text}",
        )
    else:
        raise Abort(
            f"Deploy request failed with status {response.status_code}: {response.text}",
            subject="Deploy Failed",
            log_message=f"Deploy failed: {response.status_code} - {response.text}",
        )


async def _deploy_from_api(ctx: typer.Context, cluster_name: str):
    """Deploy using settings fetched from API."""
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    # Get the cluster (use get_cluster_by_name to fetch client_secret and sssd_binder_password)
    console.print(f"[dim]Fetching cluster '{cluster_name}'...[/dim]")
    cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)

    if not cluster:
        raise Abort(
            f"Cluster '{cluster_name}' not found.",
            subject="Cluster Not Found",
            log_message=f"Cluster not found: {cluster_name}",
        )

    # Get the cloud account to determine the provider
    cloud_account_id = cluster.cloud_account_id
    if not cloud_account_id:
        raise Abort(
            "Cluster does not have a cloud account ID.",
            subject="Missing Cloud Account",
            log_message="Cluster missing cloud_account_id",
        )

    cloud_account = await cloud_account_sdk.get(ctx, int(cloud_account_id))
    if not cloud_account:
        raise Abort(
            f"Cloud account '{cloud_account_id}' not found.",
            subject="Cloud Account Not Found",
            log_message=f"Cloud account not found: {cloud_account_id}",
        )

    provider = cloud_account.provider.lower() if cloud_account.provider else ""
    if not provider:
        raise Abort(
            "Cloud account does not have a provider set.",
            subject="Missing Provider",
            log_message="Cloud account missing provider",
        )

    # Recover the actual cloud type from additional_attributes
    # (e.g., on_prem -> microk8s when vantage_cloud_type is stashed)
    cloud_attrs = cloud_account.attributes or {}
    if "vantage_cloud_type" in cloud_attrs:
        provider = cloud_attrs["vantage_cloud_type"]

    # Get settings from creationParameters
    creation_params = cluster.creation_parameters or {}
    settings_dict = creation_params.get("settings", {})

    # Add required fields
    settings_dict["provider"] = provider
    settings_dict["cluster_name"] = cluster.name

    # Validate and add keycloak and SSSD credentials from cluster
    if not cluster.client_secret:
        raise Abort(
            "Cluster is missing client secret. Please check cluster configuration.",
            subject="Missing Credentials",
            log_message="Cluster missing client_secret",
        )
    if not cluster.sssd_binder_password:
        raise Abort(
            "Cluster is missing SSSD binder password. Please check organization settings.",
            subject="Missing Credentials",
            log_message="Cluster missing sssd_binder_password",
        )

    settings_dict["keycloak_client_id"] = cluster.client_id
    settings_dict["keycloak_client_secret"] = cluster.client_secret
    # settings_dict["keycloak_organization_id"] = ctx.obj.persona.identity_data.org_id
    # settings_dict["keycloak_organization_name"] = ctx.obj.persona.identity_data.org_name
    settings_dict["sssd_binder_password"] = cluster.sssd_binder_password

    # Pass the JupyterHub service token from creation_parameters so vdeployer
    # uses the same token the Vantage API expects (instead of generating a random one)
    if jupyterhub_token := creation_params.get("jupyterhub_token"):
        settings_dict["jupyterhub_service_token"] = jupyterhub_token

    # Construct the vdeployer-web URL
    vdeployer_url = get_vdeployer_web_url(
        client_id=cluster.client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )
    deploy_url = f"{vdeployer_url}/deploy"

    console.print("[dim]Sending deploy request to vdeployer-web...[/dim]")
    console.print(f"[dim]URL: {deploy_url}[/dim]")

    # Make the POST request to /deploy
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(
            deploy_url,
            json={"settings": settings_dict},
            headers={"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"},
        )

    if response.status_code == 200:
        result = response.json()
        formatter.success(f"Deploy triggered successfully: {result.get('message', 'OK')}")

        # Build display data with settings flattened
        display_data = {
            "cluster": cluster_name,
            "client_id": cluster.client_id,
            "provider": provider,
            "vdeployer_url": vdeployer_url,
        }
        # Add each setting as a separate row with "settings." prefix
        for key, value in settings_dict.items():
            display_data[f"settings.{key}"] = value

        formatter.render_get(
            data=display_data,
            resource_name="Deploy Request",
        )
    elif response.status_code == 409:
        result = response.json()
        raise Abort(
            f"Deploy conflict: {result.get('detail', 'A task is already running')}",
            subject="Deploy Conflict",
            log_message=f"Deploy conflict: {response.text}",
        )
    else:
        raise Abort(
            f"Deploy request failed with status {response.status_code}: {response.text}",
            subject="Deploy Failed",
            log_message=f"Deploy failed: {response.status_code} - {response.text}",
        )
