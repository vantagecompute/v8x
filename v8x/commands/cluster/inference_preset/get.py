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
"""Get inference preset command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.inference_preset import inference_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_inference_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the inference preset"),
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
    """Get details of a specific inference preset.

    Examples:
        v8x cluster preset get cpu-small --cluster my-cluster
    """
    console = ctx.obj.console

    try:
        response = await inference_preset_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(
                f"[yellow]Inference preset '{name}' not found on '{cluster_name}'[/yellow]"
            )
            return

        if response.status_code != 200:
            raise Abort(
                f"Failed to get preset: {response.text}",
                subject="API Error",
            )

        data = response.json()

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Name", data.get("name", ""))
        table.add_row("Description", data.get("description", "") or "[dim]-[/dim]")
        table.add_row("CPU", data.get("cpu", ""))
        table.add_row("Memory", data.get("memory", ""))
        table.add_row("GPU Count", str(data.get("gpu_count", 0)))
        table.add_row("Compute Pool", data.get("compute_pool", ""))
        table.add_row("Min Replicas", str(data.get("min_replicas", 1)))
        table.add_row("Max Replicas", str(data.get("max_replicas", 1)))
        table.add_row("Runtimes", ", ".join(data.get("runtimes", [])))
        if data.get("configurations"):
            table.add_row("Configurations", ", ".join(data["configurations"]))

        console.print(Panel(table, title=f"Inference Preset: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get inference preset '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
