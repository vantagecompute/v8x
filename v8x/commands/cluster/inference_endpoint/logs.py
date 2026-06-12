# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get inference endpoint logs."""

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
async def logs_inference(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Endpoint name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of log lines")] = 200,
    container: Annotated[
        str, typer.Option("--container", help="Container name")
    ] = "kserve-container",
):
    """Tail logs from an inference endpoint.

    Examples:
        v8x cluster inference-endpoint logs my-endpoint -c my-cluster
        v8x cluster inference-endpoint logs my-endpoint -c my-cluster -n 500
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/inferences/{name}:logs"

        async with get_http_client() as client:
            response = await client.get(
                url,
                params={"n_lines": lines, "container": container},
                headers=get_auth_headers(ctx),
            )

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        log_text = data.get("logs", "")
        if data.get("truncated"):
            console.print(f"[yellow]Showing last {lines} lines (truncated)[/yellow]")
        console.print(log_text)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get logs.", details={"error": str(e)}
        )
