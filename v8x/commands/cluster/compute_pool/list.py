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
"""List compute pools command."""

from typing import Optional

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
async def list_compute_pools(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    workload: Annotated[
        Optional[str],
        typer.Option(
            "--workload",
            "-w",
            help="Filter by workload type (comma-delimited, e.g. 'kubeflow-workspace,cloud-shell')",
        ),
    ] = None,
):
    """List all compute pools configured within a Vantage K8s cluster.

    Examples:
        v8x cluster compute-pool list --cluster my-cluster
        v8x cluster compute-pool list -c my-cluster --workload kubeflow-workspace
    """
    console = ctx.obj.console

    try:
        response = await compute_pool_sdk.list(
            ctx,
            cluster_name=cluster_name,
            workload=workload,
        )

        if response.status_code != 200:
            raise Abort(
                f"Failed to list compute pools: {response.text}",
                subject="API Error",
            )

        data = response.json() or []
        groups = data if isinstance(data, list) else data.get("node_groups", [])

        if not groups:
            console.print(f"No compute pools found on '{cluster_name}'")
            return

        from rich.table import Table

        table = Table(title=f"Compute Pools on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Instance Type")
        table.add_column("Min", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Workload")
        table.add_column("GPU")
        table.add_column("GPU Count", justify="right")

        for g in groups:
            labels = g.get("labels", {})
            workload_type = labels.get("vc.workload-type", labels.get("vc.workload", ""))

            table.add_row(
                g["name"],
                g.get("instance_type", "") or "[dim]-[/dim]",
                str(g.get("min_size", 0)),
                str(g.get("max_size", 10)),
                workload_type or "[dim]-[/dim]",
                "[green]yes[/green]" if g.get("is_gpu") else "[dim]no[/dim]",
                str(g.get("gpu_count", 0)) if g.get("gpu_count") else "[dim]-[/dim]",
            )

        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list compute pools on '{cluster_name}'.",
            details={"error": str(e)},
        )
