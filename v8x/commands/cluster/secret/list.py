# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List secrets command."""

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
async def list_secrets(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    secret_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter: huggingface or s3")
    ] = None,
):
    """List secrets in your profile namespace.

    Examples:
        v8x cluster secret list -c my-cluster
        v8x cluster secret list -c my-cluster --type huggingface
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/secrets"
        params = {}
        if secret_type:
            params["type"] = secret_type

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
            console.print("No secrets found")
            return

        from rich.table import Table

        table = Table(title=f"Secrets on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Type")
        table.add_column("Namespace")
        table.add_column("Owner")
        table.add_column("Default")
        table.add_column("Platform")

        for s in items:
            table.add_row(
                s.get("name", ""),
                s.get("type", ""),
                s.get("namespace", ""),
                s.get("owner", "") or "[dim]-[/dim]",
                "[green]yes[/green]" if s.get("is_default") else "[dim]no[/dim]",
                "[cyan]yes[/cyan]" if s.get("is_platform_managed") else "[dim]no[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list secrets.", details={"error": str(e)}
        )
