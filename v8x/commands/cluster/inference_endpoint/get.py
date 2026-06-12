# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get inference endpoint."""

import json

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
async def get_inference(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Endpoint name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get details of an inference endpoint.

    Examples:
        v8x cluster inference-endpoint get my-endpoint -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/inferences/{name}"

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code == 404:
            console.print(f"[yellow]Inference '{name}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Name", data.get("name", ""))
        table.add_row("Kind", data.get("kind", ""))
        table.add_row("Owner", data.get("owner", ""))
        table.add_row("Phase", data.get("status", {}).get("phase", ""))
        table.add_row("URL", data.get("url", ""))
        table.add_row("Compute Pool", data.get("compute_pool", "") or "-")
        sizing = data.get("sizing", {})
        table.add_row("CPU", sizing.get("cpu", ""))
        table.add_row("Memory", sizing.get("memory", ""))
        gpus = sizing.get("gpus")
        if gpus and gpus.get("num"):
            table.add_row("GPUs", f"{gpus['num']}× {gpus.get('vendor', 'nvidia')}")
        table.add_row(
            "Replicas", f"{sizing.get('min_replicas', 1)}-{sizing.get('max_replicas', 1)}"
        )
        table.add_row(
            "Stopped", "[yellow]yes[/yellow]" if data.get("stopped") else "[dim]no[/dim]"
        )

        console.print(Panel(table, title=f"Inference: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get inference.", details={"error": str(e)}
        )
