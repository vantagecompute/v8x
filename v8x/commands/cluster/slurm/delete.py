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
"""Delete Slurm cluster command."""

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
async def delete_slurm_cluster(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the Slurm cluster to delete"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """Remove a Slurm cluster and all its resources.

    This deletes the Slurm cluster namespace and all components deployed within it.
    This is a background operation — the namespace will be removed asynchronously.

    Examples:
        v8x cluster slurm delete hpc-prod --cluster my-cluster
        v8x cluster slurm delete ml-dev -c my-cluster --yes
    """
    console = ctx.obj.console

    if not yes:
        confirm = typer.confirm(
            f"Are you sure you want to delete Slurm cluster '{name}' on '{cluster_name}'?"
        )
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        vdeployer_settings = await build_vdeployer_settings(ctx, cluster)

        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        url = f"{vdeployer_url}/slurm-cluster/{name}"

        request_data = {
            "settings": vdeployer_settings,
        }

        console.print(f"[dim]Deleting Slurm cluster '{name}' on '{cluster_name}'...[/dim]")

        async with get_http_client() as client:
            response = await client.request(
                "DELETE",
                url,
                json=request_data,
                headers=get_auth_headers(ctx),
            )

        if response.status_code == 200:
            result = response.json()
            console.print(
                f"[green]✓[/green] {result.get('message', f'Slurm cluster {name} deletion started')}"
            )
        elif response.status_code == 404:
            result = response.json()
            console.print(
                f"[yellow]Not found:[/yellow] {result.get('detail', 'Cluster not found')}"
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

        # Remove the cluster registration from vantage-api. Run regardless of
        # the vdeployer-web result: in orphaned-state recovery the k8s workload
        # may already be gone (404/409) while the DB record lingers, and the
        # user's expectation is that `cluster slurm delete` always clears both.
        console.print(
            f"[dim]Removing Slurm cluster '{name}' registration from vantage-api...[/dim]"
        )
        try:
            api_result = await cluster_sdk.delete_slurm_cluster_in_k8s(
                ctx, name=name, parent_cluster_name=cluster_name
            )
            console.print(
                f"[green]✓[/green] {api_result.get('message', 'API registration removed')}"
            )
        except Exception as api_err:
            console.print(f"[red]Error:[/red] vantage-api deletion failed: {api_err}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
