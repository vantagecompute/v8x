# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List Ray jobs."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.ray_job import ray_job_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_ray_jobs(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List Ray jobs.

    Examples:
        v8x cluster ray list -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await ray_job_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        items = response.json()
        if not isinstance(items, list):
            items = items.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No Ray jobs found")
            return

        from rich.table import Table

        table = Table(title=f"Ray Jobs on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Deployment")
        table.add_column("Workers", justify="right")
        table.add_column("Ray Cluster")
        table.add_column("Dashboard")

        for job in items:
            table.add_row(
                job.get("name", ""),
                job.get("status", "") or "[dim]-[/dim]",
                job.get("deployment_status", "") or "[dim]-[/dim]",
                str(job.get("workers", "") or "[dim]-[/dim]"),
                job.get("ray_cluster_name", "") or "[dim]-[/dim]",
                (job.get("dashboard_url", "") or "")[:50] or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list Ray jobs.", details={"error": str(e)}
        )
