# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get Dynamo deployment."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.dynamo_deployment import dynamo_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_dynamo(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Deployment name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get a Dynamo deployment.

    Examples:
        v8x cluster dynamo get my-qwen -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await dynamo_deployment_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]Dynamo deployment '{name}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        console.print(f"[bold]{data.get('name', name)}[/bold]")
        console.print(f"  Namespace:       {data.get('namespace', 'N/A')}")
        console.print(f"  Model:           {data.get('model', 'N/A')}")
        console.print(f"  Backend:         {data.get('backend', 'N/A')}")
        console.print(f"  Phase:           {data.get('phase', 'N/A')}")
        console.print(f"  Profiling Phase: {data.get('profiling_phase', 'N/A')}")
        console.print(f"  DGD:             {data.get('dgd_name', 'N/A')}")
        dgd_ready = "[green]yes[/green]" if data.get("dgd_ready") else "[yellow]no[/yellow]"
        console.print(f"  DGD Ready:       {dgd_ready}")
        console.print(f"  Compute Pool:    {data.get('compute_pool', 'N/A')}")
        console.print(f"  URL:             {data.get('url', 'N/A')}")
        conditions = data.get("conditions") or []
        if conditions:
            console.print("  Conditions:")
            for cond in conditions:
                console.print(
                    f"    {cond.get('type', '')}={cond.get('status', '')}"
                    f" {cond.get('message', '') or ''}".rstrip()
                )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get Dynamo deployment.", details={"error": str(e)}
        )
