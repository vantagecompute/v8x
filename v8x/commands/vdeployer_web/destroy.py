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
"""Destroy command for vdeployer-web."""

import httpx
import typer
from typing_extensions import Annotated
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from .deploy import get_vdeployer_web_url


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def destroy_command(
    ctx: typer.Context,
    cluster_name: Annotated[
        str, typer.Argument(help="Name of the cluster to destroy components on")
    ],
):
    """Trigger a destroy operation on a cluster via vdeployer-web.

    This command retrieves the cluster's settings from creationParameters
    and sends them to the vdeployer-web /destroy endpoint to trigger
    a destruction of Vantage K8S infrastructure components.

    Example:
        v8x vdeployer-web destroy my-cluster
    """
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    try:
        # Get the cluster
        console.print(f"[dim]Fetching cluster '{cluster_name}'...[/dim]")
        cluster = await cluster_sdk.get(ctx, cluster_name)

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
        cloud_attrs = cloud_account.attributes or {}
        if "vantage_cloud_type" in cloud_attrs:
            provider = cloud_attrs["vantage_cloud_type"]
        # Map microk8s -> k8s for vdeployer-web compatibility
        if provider == "microk8s":
            provider = "k8s"

        # Get settings from creationParameters
        creation_params = cluster.creation_parameters or {}
        settings_dict = creation_params.get("settings", {})

        # Add required fields
        settings_dict["provider"] = provider
        settings_dict["cluster_name"] = cluster.name

        # Construct the vdeployer-web URL
        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        destroy_url = f"{vdeployer_url}/destroy"

        console.print("[dim]Sending destroy request to vdeployer-web...[/dim]")
        console.print(f"[dim]URL: {destroy_url}[/dim]")

        # Make the POST request to /destroy (authenticated)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                destroy_url,
                json={"settings": settings_dict},
                headers={"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"},
            )

        if response.status_code == 200:
            result = response.json()
            formatter.success(f"Destroy triggered successfully: {result.get('message', 'OK')}")
            formatter.render_get(
                data={
                    "cluster": cluster_name,
                    "client_id": cluster.client_id,
                    "provider": provider,
                    "vdeployer_url": vdeployer_url,
                },
                resource_name="Destroy Request",
            )
        elif response.status_code == 409:
            result = response.json()
            raise Abort(
                f"Destroy conflict: {result.get('detail', 'A task is already running')}",
                subject="Destroy Conflict",
                log_message=f"Destroy conflict: {response.text}",
            )
        else:
            raise Abort(
                f"Destroy request failed with status {response.status_code}: {response.text}",
                subject="Destroy Failed",
                log_message=f"Destroy failed: {response.status_code} - {response.text}",
            )

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
