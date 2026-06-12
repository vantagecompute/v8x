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
"""Delete workspace preset command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.workspace_preset import workspace_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_workspace_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the workspace preset to delete"),
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
    """Delete a workspace preset from a Vantage cluster.

    Examples:
        v8x cluster workspace-preset delete my-jupyterlab --cluster my-cluster
        v8x cluster workspace-preset delete my-codeserver -c my-cluster --force
    """
    console = ctx.obj.console

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete workspace preset '{name}'?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        console.print(f"[dim]Deleting workspace preset '{name}' from '{cluster_name}'...[/dim]")

        response = await workspace_preset_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Workspace preset '{name}' deleted")
        elif response.status_code == 404:
            console.print(
                f"[yellow]Workspace preset '{name}' not found on '{cluster_name}'[/yellow]"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete workspace preset '{name}' from '{cluster_name}'.",
            details={"error": str(e)},
        )
