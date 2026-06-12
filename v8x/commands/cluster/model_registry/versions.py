# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List model versions."""

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
async def list_model_versions(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Model name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List versions of a model.

    Examples:
        v8x cluster model-registry versions gemma-4b -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model/{name}/versions"

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        items = data.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print(f"No versions found for '{name}'")
            return

        from rich.table import Table

        table = Table(title=f"Versions of '{name}'")
        table.add_column("Version", style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Size")
        table.add_column("Last Modified")

        for m in items:
            size = m.get("size_bytes")
            table.add_row(
                m.get("version", ""),
                m.get("id", ""),
                f"{size / 1e9:.1f} GB" if size else "[dim]-[/dim]",
                m.get("last_modified", "") or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list versions.", details={"error": str(e)}
        )
