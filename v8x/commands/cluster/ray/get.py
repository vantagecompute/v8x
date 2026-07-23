# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get Ray job."""

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
async def get_ray_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="RayJob name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get a Ray job.

    Examples:
        v8x cluster ray get train-1 -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await ray_job_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]Ray job '{name}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        console.print(f"[bold]{data.get('name', name)}[/bold]")
        console.print(f"  Namespace:    {data.get('namespace', 'N/A')}")
        console.print(f"  Entrypoint:   {data.get('entrypoint', 'N/A')}")
        console.print(f"  Image:        {data.get('image', 'N/A')}")
        console.print(f"  Status:       {data.get('status', 'N/A')}")
        console.print(f"  Deployment:   {data.get('deployment_status', 'N/A')}")
        console.print(f"  Ray Cluster:  {data.get('ray_cluster_name', 'N/A')}")
        console.print(f"  Workers:      {data.get('workers', 'N/A')}")
        console.print(f"  Dashboard:    {data.get('dashboard_url', 'N/A')}")
        console.print(f"  Preset:       {data.get('configuration_preset') or 'N/A'}")
        console.print(f"  Start Time:   {data.get('start_time') or 'N/A'}")
        console.print(f"  End Time:     {data.get('end_time') or 'N/A'}")
        endpoints = data.get("model_endpoints") or []
        if endpoints:
            console.print("  Model Endpoints:")
            for ep in endpoints:
                console.print(
                    f"    {ep.get('name', '')} ({ep.get('platform', '')}/"
                    f"{ep.get('deployment', '')}) → {ep.get('env_var', '')}={ep.get('url', '')}"
                )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get Ray job.", details={"error": str(e)}
        )
