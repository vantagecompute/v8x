# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List models."""

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
async def list_models(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    name_filter: Annotated[
        str | None, typer.Option("--name", help="Filter by name prefix")
    ] = None,
):
    """List all models in the registry.

    Examples:
        v8x cluster model-registry list -c my-cluster
        v8x cluster model-registry list -c my-cluster --name gemma
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model"
        params = {}
        if name_filter:
            params["name"] = name_filter

        async with get_http_client() as client:
            response = await client.get(url, params=params, headers=get_auth_headers(ctx))

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        items = data.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No models found")
            return

        from rich.table import Table

        table = Table(title=f"Models on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Version")
        table.add_column("Size")
        table.add_column("Files", justify="right")
        table.add_column("Description")

        for m in items:
            size = m.get("size_bytes")
            size_str = f"{size / 1e9:.1f} GB" if size else "[dim]-[/dim]"
            table.add_row(
                m.get("name", ""),
                m.get("version", ""),
                size_str,
                str(m.get("file_count", "")) or "[dim]-[/dim]",
                (m.get("description") or "")[:40] or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list models.", details={"error": str(e)}
        )
