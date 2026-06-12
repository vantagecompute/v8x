# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get model details."""

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
async def get_model(
    ctx: typer.Context,
    model_id: Annotated[str, typer.Argument(help="Model name or ID")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get details of a model.

    Examples:
        v8x cluster model-registry get gemma-4b -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model/{model_id}"

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code == 404:
            console.print(f"[yellow]Model '{model_id}' not found[/yellow]")
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
        for field in ["name", "version", "artifact_uri", "description"]:
            if val := data.get(field):
                table.add_row(field.replace("_", " ").title(), str(val))
        if size := data.get("size_bytes"):
            table.add_row("Size", f"{size / 1e9:.2f} GB")
        if fc := data.get("file_count"):
            table.add_row("Files", str(fc))

        console.print(Panel(table, title=f"Model: {model_id}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get model.", details={"error": str(e)}
        )
