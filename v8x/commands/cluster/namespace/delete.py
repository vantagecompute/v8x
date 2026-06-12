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
"""Delete namespace command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.namespace import namespace_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_namespace(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Namespace name to delete")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
):
    """Delete a namespace from a Vantage cluster.

    Examples:
        v8x cluster namespace delete my-namespace -c my-cluster
        v8x cluster namespace delete my-namespace -c my-cluster --force
    """
    console = ctx.obj.console

    if not force:
        confirm = typer.confirm(f"Delete namespace '{name}'? This is destructive.")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        response = await namespace_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Namespace '{name}' deleted")
        elif response.status_code == 404:
            console.print(f"[yellow]Namespace '{name}' not found[/yellow]")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete namespace '{name}'.",
            details={"error": str(e)},
        )
