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
"""Deploy Kubeflow command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import (
    build_vdeployer_settings,
    get_auth_headers,
    get_cluster_with_creds,
    get_http_client,
    get_vdeployer_web_url,
)


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_kubeflow(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    admin_node_group: Annotated[
        str | None,
        typer.Option(
            "--admin-node-group",
            help="Node group for Kubeflow infrastructure pods (controllers, dashboard). "
            "If not set, pods run on control-plane nodes.",
        ),
    ] = None,
):
    """Deploy Kubeflow on a Vantage K8s cluster.

    Triggers the Kubeflow deployment via vdeployer-web. This is a background
    operation — use 'v8x cluster kubeflow get' to check status.

    Examples:
        v8x cluster kubeflow create --cluster my-cluster
        v8x cluster kubeflow create --cluster my-cluster --admin-node-group kubeflow-admin
    """
    console = ctx.obj.console

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)

        # Persist kubeflow_enabled=true in cluster settings (mirrors 'service enable')
        creation_params = cluster.creation_parameters or {}
        existing_settings = dict(creation_params.get("settings", {}))
        if not existing_settings.get("kubeflow_enabled", False):
            existing_settings["kubeflow_enabled"] = True
            await cluster_sdk.update_cluster(ctx, name=cluster_name, settings=existing_settings)
            console.print("[dim]Updated cluster settings: kubeflow_enabled=true[/dim]")

        vdeployer_settings = await build_vdeployer_settings(ctx, cluster)

        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        url = f"{vdeployer_url}/kubeflow"

        request_data: dict = {"settings": vdeployer_settings}
        if admin_node_group:
            request_data["admin_node_group"] = admin_node_group

        if admin_node_group:
            console.print(
                f"[dim]Deploying Kubeflow on '{cluster_name}' (admin node group: {admin_node_group})...[/dim]"
            )
        else:
            console.print(f"[dim]Deploying Kubeflow on '{cluster_name}'...[/dim]")

        async with get_http_client() as client:
            response = await client.post(
                url,
                json=request_data,
                headers=get_auth_headers(ctx),
            )

        if response.status_code == 200:
            result = response.json()
            console.print(
                f"[green]\u2713[/green] {result.get('message', 'Kubeflow deployment started')}"
            )
        elif response.status_code == 409:
            result = response.json()
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to deploy Kubeflow on '{cluster_name}'.",
            details={"error": str(e)},
        )
