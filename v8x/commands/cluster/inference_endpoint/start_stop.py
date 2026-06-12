# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Start/stop inference endpoints."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import (
    get_auth_headers,
    get_cluster_with_creds,
    get_http_client,
    get_vdeployer_web_url,
)


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def start_inference(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Endpoint name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Start (resume) a stopped inference endpoint.

    Examples:
        v8x cluster inference-endpoint start my-endpoint -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/inferences/{name}:start"

        async with get_http_client() as client:
            response = await client.post(url, headers=get_auth_headers(ctx))

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Inference '{name}' started")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(error_message="Failed to start.", details={"error": str(e)})


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def stop_inference(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Endpoint name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Stop an inference endpoint.

    Examples:
        v8x cluster inference-endpoint stop my-endpoint -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/inferences/{name}:stop"

        async with get_http_client() as client:
            response = await client.post(url, headers=get_auth_headers(ctx))

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Inference '{name}' stopped")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(error_message="Failed to stop.", details={"error": str(e)})
