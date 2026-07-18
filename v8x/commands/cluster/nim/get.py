# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get NIM deployment."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nim_deployment import nim_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_nim(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Deployment name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get a NIM deployment.

    Examples:
        v8x cluster nim get my-llama -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await nim_deployment_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]NIM deployment '{name}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        ing = data.get("ingress", {}) or {}
        replicas = data.get("replicas", {}) or {}
        console.print(f"[bold]{data.get('name', name)}[/bold]")
        console.print(f"  Namespace: {data.get('namespace', 'N/A')}")
        console.print(f"  Model:     {data.get('catalog_id', 'N/A')}")
        console.print(f"  Version:   {data.get('version', 'N/A')}")
        console.print(f"  Platform:  {data.get('platform', 'N/A')}")
        console.print(
            f"  Replicas:  {replicas.get('minimum', 'N/A')}-{replicas.get('maximum', 'N/A')}"
        )
        console.print(f"  Ingress:   {ing.get('type', 'N/A')} (auth: {ing.get('auth', 'N/A')})")
        console.print(f"  Status:    {data.get('status', 'N/A')}")
        console.print(
            f"  Ready:     {'[green]yes[/green]' if data.get('ready') else '[yellow]no[/yellow]'}"
        )
        console.print(f"  URL:       {data.get('url', 'N/A')}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get NIM deployment.", details={"error": str(e)}
        )
