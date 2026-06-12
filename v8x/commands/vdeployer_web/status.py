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
"""Status command for vdeployer-web."""

import httpx
import typer
from typing_extensions import Annotated
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
async def status_command(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Name of the cluster to check status for")],
):
    """Get the status of vdeployer-web on a cluster.

    This command queries the vdeployer-web /status endpoint to check
    the current state of deployment/destroy operations.

    Example:
        v8x vdeployer-web status my-cluster
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

        # Construct the vdeployer-web URL
        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        status_url = f"{vdeployer_url}/status"

        console.print("[dim]Querying vdeployer-web status...[/dim]")
        console.print(f"[dim]URL: {status_url}[/dim]")

        # Make the GET request to /status (authenticated)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                status_url,
                headers={"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"},
            )

        if response.status_code == 200:
            result = response.json()
            formatter.success("VDeployer-web status retrieved successfully")
            formatter.render_get(
                data={
                    "cluster": cluster_name,
                    "client_id": cluster.client_id,
                    "vdeployer_url": vdeployer_url,
                    **result,
                },
                resource_name="VDeployer-Web Status",
            )
        else:
            raise Abort(
                f"Status request failed with status {response.status_code}: {response.text}",
                subject="Status Failed",
                log_message=f"Status failed: {response.status_code} - {response.text}",
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
