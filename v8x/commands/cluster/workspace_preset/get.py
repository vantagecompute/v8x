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
"""Get workspace preset command."""

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
async def get_workspace_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the workspace preset"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
):
    """Get details of a specific workspace preset.

    Examples:
        v8x cluster workspace-preset get platform-jupyterlab --cluster my-cluster
    """
    console = ctx.obj.console

    try:
        response = await workspace_preset_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(
                f"[yellow]Workspace preset '{name}' not found on '{cluster_name}'[/yellow]"
            )
            return

        if response.status_code != 200:
            raise Abort(
                f"Failed to get workspace preset: {response.text}",
                subject="API Error",
            )

        data = response.json()

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Name", data.get("name", ""))
        table.add_row("Display Name", data.get("display_name", ""))
        table.add_row("Description", data.get("description", ""))
        table.add_row("IDE Type", data.get("ide_type", "") or "[dim]-[/dim]")
        table.add_row("Owner", data.get("owner", "") or "[dim]platform[/dim]")
        table.add_row("Home PVC", data.get("home_pvc", ""))
        table.add_row(
            "Hidden",
            "[yellow]yes[/yellow]" if data.get("hidden") else "[dim]no[/dim]",
        )
        table.add_row(
            "Deprecated",
            "[yellow]yes[/yellow]" if data.get("deprecated") else "[dim]no[/dim]",
        )

        # Show pod template / pod sizes if available
        pod_template = data.get("pod_template", {})
        if pod_sizes := pod_template.get("pod_config", {}).get("values", []):
            sizes_str = ", ".join(
                f"{s.get('display_name', '?')} ({s.get('spec', {}).get('resources', {}).get('requests', {}).get('cpu', '?')} CPU, "
                f"{s.get('spec', {}).get('resources', {}).get('requests', {}).get('memory', '?')} RAM)"
                for s in pod_sizes
            )
            table.add_row("Pod Sizes", sizes_str)

        if data_pvcs := data.get("data_pvcs", []):
            pvcs_str = ", ".join(
                f"{p.get('pvc_name', '?')}→{p.get('mount_path', '?')}" for p in data_pvcs
            )
            table.add_row("Data PVCs", pvcs_str)

        console.print(Panel(table, title=f"Workspace Preset: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get workspace preset '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
