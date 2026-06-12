# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get secret command."""

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
async def get_secret(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get details of a secret (value is never returned).

    Examples:
        v8x cluster secret get hf-token -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/secrets/{name}"

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code == 404:
            console.print(f"[yellow]Secret '{name}' not found[/yellow]")
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

        for field in ["name", "type", "namespace", "owner", "created_at", "last_used_at"]:
            if val := data.get(field):
                table.add_row(field.replace("_", " ").title(), str(val))
        if data.get("region"):
            table.add_row("Region", data["region"])
        if data.get("endpoint_url"):
            table.add_row("Endpoint URL", data["endpoint_url"])
        table.add_row(
            "Default", "[green]yes[/green]" if data.get("is_default") else "[dim]no[/dim]"
        )
        table.add_row(
            "Platform Managed",
            "[cyan]yes[/cyan]" if data.get("is_platform_managed") else "[dim]no[/dim]",
        )

        console.print(Panel(table, title=f"Secret: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get secret.", details={"error": str(e)}
        )
