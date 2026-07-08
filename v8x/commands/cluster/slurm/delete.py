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
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.slurm import slurm_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


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
        console.print(f"[dim]Deleting Slurm cluster '{name}' on '{cluster_name}'...[/dim]")
        result = await slurm_sdk.delete(ctx, cluster_name=cluster_name, name=name)
        response = result.response

        if response.status_code == 200:
            data = response.json() or {}
            console.print(
                f"[green]✓[/green] {data.get('message', f'Slurm cluster {name} deletion started')}"
            )
        elif response.status_code == 404:
            data = response.json() or {}
            console.print(f"[yellow]Not found:[/yellow] {data.get('detail', 'Cluster not found')}")
        elif response.status_code == 409:
            data = response.json() or {}
            console.print(
                f"[yellow]Warning:[/yellow] {data.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

        if result.api_result:
            console.print(
                f"[green]✓[/green] {result.api_result.get('message', 'API registration removed')}"
            )
        if result.api_error:
            console.print(f"[red]Error:[/red] vantage-api deletion failed: {result.api_error}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
