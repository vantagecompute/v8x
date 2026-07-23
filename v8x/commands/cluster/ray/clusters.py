# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List/get Ray clusters."""

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
async def clusters_ray(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    name: Annotated[str | None, typer.Argument(help="RayCluster name (omit to list all)")] = None,
):
    """List Ray clusters, or show one by name.

    Examples:
        v8x cluster ray clusters -c my-cluster
        v8x cluster ray clusters train-1-raycluster -c my-cluster
    """
    console = ctx.obj.console
    try:
        if name:
            response = await ray_job_sdk.get_cluster(ctx, cluster_name=cluster_name, name=name)
            if response.status_code == 404:
                console.print(f"[yellow]Ray cluster '{name}' not found[/yellow]")
                return
            if response.status_code != 200:
                raise Abort(f"Failed: {response.text}", subject="API Error")

            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
                return

            console.print(f"[bold]{data.get('name', name)}[/bold]")
            console.print(f"  Namespace:       {data.get('namespace', 'N/A')}")
            console.print(f"  State:           {data.get('state', 'N/A')}")
            console.print(f"  Desired Workers: {data.get('desired_workers', 'N/A')}")
            console.print(f"  Ready Workers:   {data.get('ready_workers', 'N/A')}")
            console.print(f"  Head Service IP: {data.get('head_service_ip') or 'N/A'}")
            console.print(f"  Created:         {data.get('created_at') or 'N/A'}")
            return

        response = await ray_job_sdk.list_clusters(ctx, cluster_name=cluster_name)
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        items = response.json()
        if not isinstance(items, list):
            items = items.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No Ray clusters found")
            return

        from rich.table import Table

        table = Table(title=f"Ray Clusters on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("State")
        table.add_column("Desired", justify="right")
        table.add_column("Ready", justify="right")
        table.add_column("Head IP")

        for rc in items:
            table.add_row(
                rc.get("name", ""),
                rc.get("state", "") or "[dim]-[/dim]",
                str(rc.get("desired_workers", "") or 0),
                str(rc.get("ready_workers", "") or 0),
                rc.get("head_service_ip", "") or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list Ray clusters.", details={"error": str(e)}
        )
