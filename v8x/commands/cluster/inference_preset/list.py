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
"""List inference presets command."""

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
async def list_inference_presets(
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
    """List all inference presets on a Vantage cluster.

    Examples:
        v8x cluster preset list --cluster my-cluster
    """
    console = ctx.obj.console

    try:
        response = await inference_preset_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(
                f"Failed to list presets: {response.text}",
                subject="API Error",
            )

        data = response.json()
        items = data.get("items", [])

        if not items:
            console.print(f"No inference presets found on '{cluster_name}'")
            return

        from rich.table import Table

        table = Table(title=f"Inference Presets on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("CPU")
        table.add_column("Memory")
        table.add_column("GPUs", justify="right")
        table.add_column("Compute Pool")
        table.add_column("Replicas")
        table.add_column("Runtimes")

        for p in items:
            table.add_row(
                p.get("name", ""),
                p.get("cpu", ""),
                p.get("memory", ""),
                str(p.get("gpu_count", 0)),
                p.get("compute_pool", ""),
                f"{p.get('min_replicas', 1)}-{p.get('max_replicas', 1)}",
                ", ".join(p.get("runtimes", [])),
            )

        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list inference presets on '{cluster_name}'.",
            details={"error": str(e)},
        )
