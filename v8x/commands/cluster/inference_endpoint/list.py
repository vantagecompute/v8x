# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List inference endpoints."""

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
async def list_inferences(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List inference endpoints.

    Examples:
        v8x cluster inference-endpoint list -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = (
            f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/inferences"
        )

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        items = response.json()
        if not isinstance(items, list):
            items = items.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No inference endpoints found")
            return

        from rich.table import Table

        table = Table(title=f"Inference Endpoints on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Kind")
        table.add_column("Phase")
        table.add_column("Replicas")
        table.add_column("Compute Pool")
        table.add_column("URL")

        for ep in items:
            status = ep.get("status", {})
            table.add_row(
                ep.get("name", ""),
                ep.get("kind", ""),
                status.get("phase", ""),
                f"{status.get('ready_replicas', 0)}/{status.get('available_replicas', 0)}",
                ep.get("compute_pool", "") or "[dim]-[/dim]",
                (ep.get("url", "") or "")[:40] or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list inferences.", details={"error": str(e)}
        )
