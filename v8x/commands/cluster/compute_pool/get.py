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
"""Get compute pool command."""

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
async def get_compute_pool(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the compute pool"),
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
    """Get details of a specific compute pool.

    Examples:
        v8x cluster compute-pool get workspace-md --cluster my-cluster
        v8x cluster compute-pool get desktop-lg -c my-cluster
    """
    console = ctx.obj.console

    try:
        response = await compute_pool_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]Compute pool '{name}' not found on '{cluster_name}'[/yellow]")
            return

        if response.status_code != 200:
            raise Abort(
                f"Failed to get compute pool: {response.text}",
                subject="API Error",
            )

        data = response.json() or {}

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Name", data["name"])
        table.add_row("Min Size", str(data.get("min_size", 0)))
        table.add_row("Max Size", str(data.get("max_size", 10)))
        if data.get("instance_type"):
            table.add_row("Instance Type", data["instance_type"])
        table.add_row(
            "Control Plane",
            "[green]yes[/green]" if data.get("is_control_plane") else "[dim]no[/dim]",
        )
        table.add_row(
            "GPU",
            "[green]yes[/green]" if data.get("is_gpu") else "[dim]no[/dim]",
        )
        if data.get("gpu_count"):
            table.add_row("GPU Count", str(data["gpu_count"]))
        if data.get("labels"):
            labels_str = ", ".join(f"{k}={v}" for k, v in data["labels"].items())
            table.add_row("Labels", labels_str)
        if data.get("taints"):
            taints_str = ", ".join(
                f"{t.get('key', '')}={t.get('value', '')}:{t.get('effect', '')}"
                for t in data["taints"]
            )
            table.add_row("Taints", taints_str)

        console.print(Panel(table, title=f"Compute Pool: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get compute pool '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
