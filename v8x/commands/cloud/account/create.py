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
"""Create cloud account command."""

import json
import select
import socket
import urllib.parse
from typing import Optional

import typer
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.cloud.lxd_utils import generate_lxd_client_certificate
from vantage_sdk.cloud.schema import CloudType
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort


def _obfuscate_sensitive_attributes(attributes: dict | None) -> dict:
    """Obfuscate attributes containing 'cert' or 'key' in their name."""
    if not attributes:
        return {}
    result = {}
    for k, v in attributes.items():
        if "cert" in k.lower() or "key" in k.lower():
            result[k] = "********"
        else:
            result[k] = v
    return result


def _register_lxd_client_cert(
    lxd_server_url: str,
    lxd_token: str,
    client_cert: str,
    client_key: str,
    cluster: bool = False,
) -> None:
    """Register a client certificate with the LXD server using a trust token.

    Uses in-memory SSL handling to avoid writing cert/key to disk.

    Args:
        lxd_server_url: URL of the LXD server (e.g., https://192.168.0.55:8443)
        lxd_token: Trust token for authentication
        client_cert: PEM-encoded client certificate
        client_key: PEM-encoded client private key
        cluster: Whether the LXD server is running in cluster mode

    Raises:
        Exception: If registration fails
    """
    from OpenSSL import SSL, crypto

    parsed = urllib.parse.urlparse(lxd_server_url)
    host = parsed.hostname
    port = parsed.port or 8443

    # Create PyOpenSSL context
    openssl_ctx = SSL.Context(SSL.TLS_CLIENT_METHOD)
    openssl_ctx.set_verify(SSL.VERIFY_NONE, lambda *args: True)

    # Load cert and key from memory
    openssl_cert = crypto.load_certificate(crypto.FILETYPE_PEM, client_cert.encode())
    openssl_key = crypto.load_privatekey(crypto.FILETYPE_PEM, client_key.encode())
    openssl_ctx.use_certificate(openssl_cert)
    openssl_ctx.use_privatekey(openssl_key)

    # Create socket and wrap with PyOpenSSL
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30.0)
    conn = SSL.Connection(openssl_ctx, sock)
    conn.set_connect_state()
    conn.connect((host, port))

    # Handle handshake with retries for non-blocking SSL
    while True:
        try:
            conn.do_handshake()
            break
        except SSL.WantReadError:
            select.select([sock], [], [], 5.0)
        except SSL.WantWriteError:
            select.select([], [sock], [], 5.0)

    try:
        # Build HTTP request
        # For cluster mode, LXD uses the same /1.0/certificates endpoint
        # but may require all_projects=true to properly register across the cluster
        request_body = json.dumps({"type": "client", "trust_token": lxd_token})

        # Use different endpoint path based on cluster mode
        cert_endpoint = "/1.0/certificates"
        if cluster:
            # In cluster mode, add all_projects parameter to ensure cluster-wide registration
            cert_endpoint = "/1.0/certificates?all_projects=true"

        request = (
            f"POST {cert_endpoint} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(request_body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{request_body}"
        )
        conn.sendall(request.encode())

        # Read response
        response = b""
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                response += data
            except SSL.ZeroReturnError:
                break
            except SSL.WantReadError:
                select.select([sock], [], [], 5.0)

        # Parse response status
        response_str = response.decode("utf-8", errors="replace")
        status_line = response_str.split("\r\n")[0]
        if "200" not in status_line and "201" not in status_line:
            # Try to extract error message from JSON body
            try:
                body_start = response_str.index("\r\n\r\n") + 4
                body = response_str[body_start:]
                error_data = json.loads(body)
                error_msg = error_data.get("error", body)
            except ValueError, json.JSONDecodeError:
                error_msg = response_str[:500]
            raise Exception(f"LXD API error: {status_line} - {error_msg}")

    finally:
        conn.shutdown()
        sock.close()


@handle_abort
@attach_settings
@attach_persona
async def create_command(
    ctx: typer.Context,
    name: str = typer.Argument(
        ...,
        help="Name for the cloud account.",
    ),
    provider: str = typer.Option(
        ...,
        "--provider",
        help=f"Cloud provider type. Valid options: {', '.join(CloudType.choices())}",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Description for the cloud account.",
    ),
    attributes_json: Optional[str] = typer.Option(
        None,
        "--attributes",
        "-a",
        help="Provider attributes as JSON string. Fields depend on provider type.",
    ),
    assisted: bool = typer.Option(
        False,
        "--assisted",
        help="Create as a Vantage-assisted cloud account (AWS only).",
    ),
) -> None:
    r"""Create a new cloud account.

    Cloud accounts are organization-level registrations of cloud provider
    credentials. Each provider has different attribute requirements.

    For LXD accounts, include 'lxd_server_url' and 'lxd_token' in attributes.
    The CLI will automatically generate and register client certificates.

    Examples:
        # Create AWS account
        v8x cloud account create my-aws --provider aws \
            --attributes '{"role_arn": "arn:aws:iam::123456789012:role/VantageRole", "region": "us-east-1"}'

        # Create GCP account
        v8x cloud account create my-gcp --provider gcp \
            --attributes '{"project_id": "my-project", "region": "us-central1"}'

        # Create LXD account (auto-generates and registers client certificate)
        v8x cloud account create my-lxd --provider lxd \
            --attributes '{"lxd_server_url": "https://192.168.0.55:8443", "lxd_token": "<token>"}'

        # Create on-prem account
        v8x cloud account create my-onprem --provider on_prem
    """
    try:
        # Validate provider type
        try:
            cloud_type = CloudType.from_string(provider)
        except ValueError as e:
            raise Abort(
                str(e),
                subject="Invalid Provider",
                log_message=f"Invalid cloud type: {provider}",
            )

        # Parse JSON attributes if provided
        attributes: dict = {}
        if attributes_json:
            try:
                attributes = json.loads(attributes_json)
            except json.JSONDecodeError as e:
                raise Abort(
                    f"Invalid JSON in --attributes: {e}",
                    subject="Invalid Input",
                    log_message=f"JSON parse error: {e}",
                )

        # For LXD, validate required attributes and generate certs BEFORE creating account
        lxd_server_url: Optional[str] = None
        lxd_token: Optional[str] = None
        if cloud_type == CloudType.LXD:
            lxd_server_url = attributes.get("lxd_server_url")
            lxd_token = attributes.pop("lxd_token", None)  # Remove token, don't store it
            lxd_cluster = attributes.get("cluster", False)  # Check if cluster mode
            if not lxd_server_url or not lxd_token:
                raise Abort(
                    "LXD accounts require 'lxd_server_url' and 'lxd_token' in --attributes",
                    subject="Missing Required Attributes",
                    log_message="LXD cloud account missing server URL or token in attributes",
                )

            # Generate cert/key and register with LXD server BEFORE creating cloud account
            ctx.obj.console.print("[dim]Generating LXD client certificate...[/dim]")
            try:
                cert_pem, key_pem = generate_lxd_client_certificate()

                cluster_info = " (cluster mode)" if lxd_cluster else ""
                ctx.obj.console.print(
                    f"[dim]Registering certificate with LXD server{cluster_info}...[/dim]"
                )
                _register_lxd_client_cert(
                    lxd_server_url=lxd_server_url,
                    lxd_token=lxd_token,
                    client_cert=cert_pem,
                    client_key=key_pem,
                    cluster=lxd_cluster,
                )

                # Add certs to attributes for single create request
                attributes["lxd_client_cert"] = cert_pem
                attributes["lxd_client_key"] = key_pem

                ctx.obj.console.print(
                    "[green]✓[/green] LXD client certificate registered successfully"
                )
            except Exception as e:
                raise Abort(
                    f"Failed to register LXD client certificate: {e}",
                    subject="LXD Registration Failed",
                    log_message=f"LXD cert registration failed: {e}",
                )

        # Create the cloud account (with certs already in attributes for LXD)
        account = await cloud_account_sdk.create(
            ctx=ctx,
            name=name,
            provider=cloud_type.value,
            description=description,
            attributes=attributes if attributes else None,
            assisted=assisted,
        )

        # Render the created account (obfuscate sensitive attributes)
        # Use local attributes dict since API response may not include them
        display_attrs = attributes if attributes else account.attributes or {}
        account_data = {
            "id": account.id,
            "name": account.name,
            "provider": account.provider_display,
            "description": account.description or "N/A",
            "assisted_cloud_account": account.assisted_cloud_account,
            "attributes": _obfuscate_sensitive_attributes(display_attrs),
        }

        ctx.obj.formatter.render_create(
            data=account_data,
            resource_name="Cloud Account",
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="An unexpected error occurred while creating cloud account.",
            details={"error": str(e)},
        )
        raise typer.Exit(code=1)
