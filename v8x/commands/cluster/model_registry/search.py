# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Search HuggingFace models."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.model_registry import model_registry_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def search_models(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search term")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
):
    """Search HuggingFace Hub for models.

    Examples:
        v8x cluster model-registry search "llama 3" -c my-cluster
        v8x cluster model-registry search gemma -c my-cluster -n 5
    """
    console = ctx.obj.console
    try:
        response = await model_registry_sdk.search(
            ctx, cluster_name=cluster_name, query=query, limit=limit
        )

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        items = data.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No results")
            return

        from rich.table import Table

        table = Table(title=f"HuggingFace: '{query}'")
        table.add_column("ID", style="bold")
        table.add_column("Downloads", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Task")

        for m in items:
            table.add_row(
                m.get("id", ""),
                str(m.get("downloads", 0)),
                str(m.get("likes", 0)),
                m.get("pipeline_tag", "") or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(error_message="Search failed.", details={"error": str(e)})
