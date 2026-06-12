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
"""List Slurm clusters command."""

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
async def list_slurm_clusters(
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
    """List all Slurm clusters deployed within a Vantage K8s cluster.

    Examples:
        v8x cluster slurm list --cluster my-cluster
        v8x cluster slurm list -c my-cluster
    """
    console = ctx.obj.console

    try:
        response = await slurm_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(
                f"Failed to list Slurm clusters: {response.text}",
                subject="API Error",
                log_message=f"GET /slurm-cluster returned {response.status_code}",
            )

        data = response.json() or {}
        clusters = data.get("clusters", [])

        if not clusters:
            console.print(f"No Slurm clusters found on '{cluster_name}'")
            return

        # Render as table
        from rich.table import Table

        table = Table(title=f"Slurm Clusters on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Namespace")
        table.add_column("Status")
        table.add_column("Controller")
        table.add_column("Accounting")
        table.add_column("REST API")
        table.add_column("Compute Nodes", justify="right")

        for c in clusters:
            status_style = "green" if c["status"] == "running" else "yellow"
            table.add_row(
                c["name"],
                c["namespace"],
                f"[{status_style}]{c['status']}[/{status_style}]",
                "[green]ready[/green]" if c.get("controller_ready") else "[red]not ready[/red]",
                "[green]ready[/green]" if c.get("accounting_ready") else "[red]not ready[/red]",
                "[green]ready[/green]" if c.get("restapi_ready") else "[dim]n/a[/dim]",
                str(c.get("node_count", 0)),
            )

        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list Slurm clusters on '{cluster_name}'.",
            details={"error": str(e)},
        )
