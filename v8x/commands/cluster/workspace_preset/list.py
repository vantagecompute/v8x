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
"""List workspace presets command."""

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
async def list_workspace_presets(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
):
    """List all workspace presets on a Vantage cluster.

    Examples:
        v8x cluster workspace-preset list --cluster my-cluster
    """
    console = ctx.obj.console

    try:
        response = await workspace_preset_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(
                f"Failed to list workspace presets: {response.text}",
                subject="API Error",
            )

        data = response.json()
        kinds = data if isinstance(data, list) else data.get("items", [])

        if not kinds:
            console.print(f"No workspace presets found on '{cluster_name}'")
            return

        from rich.table import Table

        table = Table(title=f"Workspace Presets on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Display Name")
        table.add_column("IDE Type")
        table.add_column("Hidden")
        table.add_column("Deprecated")
        table.add_column("Owner")

        for k in kinds:
            table.add_row(
                k.get("name", ""),
                k.get("display_name", ""),
                k.get("ide_type", "") or "[dim]-[/dim]",
                "[yellow]yes[/yellow]" if k.get("hidden") else "[dim]no[/dim]",
                "[yellow]yes[/yellow]" if k.get("deprecated") else "[dim]no[/dim]",
                k.get("owner", "") or "[dim]platform[/dim]",
            )

        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list workspace presets on '{cluster_name}'.",
            details={"error": str(e)},
        )
