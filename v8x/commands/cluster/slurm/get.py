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
"""Get Slurm cluster command."""

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
async def get_slurm_cluster(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the Slurm cluster"),
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
    """Get the status of a specific Slurm cluster.

    Examples:
        v8x cluster slurm get hpc-prod --cluster my-cluster
        v8x cluster slurm get ml-dev -c my-cluster
    """
    console = ctx.obj.console

    try:
        response = await slurm_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]Slurm cluster '{name}' not found on '{cluster_name}'[/yellow]")
            return

        if response.status_code != 200:
            raise Abort(
                f"Failed to get Slurm cluster: {response.text}",
                subject="API Error",
                log_message=f"GET /slurm-cluster/{name} returned {response.status_code}",
            )

        data = response.json() or {}

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        status_style = "green" if data["status"] == "running" else "yellow"
        table.add_row("Name", data["name"])
        table.add_row("Namespace", data["namespace"])
        table.add_row("Status", f"[{status_style}]{data['status']}[/{status_style}]")
        table.add_row(
            "Controller",
            "[green]ready[/green]" if data.get("controller_ready") else "[red]not ready[/red]",
        )
        table.add_row(
            "Accounting",
            "[green]ready[/green]" if data.get("accounting_ready") else "[red]not ready[/red]",
        )
        table.add_row(
            "REST API",
            "[green]ready[/green]" if data.get("restapi_ready") else "[dim]n/a[/dim]",
        )
        table.add_row("Compute Nodes", str(data.get("node_count", 0)))

        console.print(Panel(table, title=f"Slurm Cluster: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
