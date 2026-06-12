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
"""Delete compute pool command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.compute_pool import compute_pool_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_compute_pool(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the compute pool to delete"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """Delete a compute pool from a Vantage K8s cluster.

    Removes the compute pool definition. Nodes currently in the pool are not
    immediately terminated but will no longer be managed by the autoscaler.

    Examples:
        v8x cluster compute-pool delete workspace-md --cluster my-cluster
        v8x cluster compute-pool delete desktop-lg -c my-cluster --force
    """
    console = ctx.obj.console

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete compute pool '{name}'?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        console.print(f"[dim]Deleting compute pool '{name}' from '{cluster_name}'...[/dim]")

        response = await compute_pool_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 200:
            data = response.json() or {}
            console.print(
                f"[green]✓[/green] {data.get('message', f'Compute pool {name!r} deleted')}"
            )
        elif response.status_code == 404:
            console.print(f"[yellow]Compute pool '{name}' not found on '{cluster_name}'[/yellow]")
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete compute pool '{name}' from '{cluster_name}'.",
            details={"error": str(e)},
        )
