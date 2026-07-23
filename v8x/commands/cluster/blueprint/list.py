# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List blueprints."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nvidia_catalogs import blueprint_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_blueprints(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter: available, roadmap"),
    ] = None,
):
    """List curated NVIDIA AI Blueprints.

    Examples:
        v8x cluster blueprint list -c my-cluster --status available
    """
    console = ctx.obj.console
    try:
        response = await blueprint_sdk.list(ctx, cluster_name=cluster_name, status=status)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        items = data.get("entries", []) if isinstance(data, dict) else data

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No blueprints found")
            return

        from rich.table import Table

        table = Table(title=f"NVIDIA AI Blueprints on '{cluster_name}'")
        table.add_column("ID", style="bold")
        table.add_column("Name")
        table.add_column("Category")
        table.add_column("Status")
        table.add_column("Preset Kind")
        table.add_column("Presets")

        for entry in items:
            status_val = entry.get("status", "")
            table.add_row(
                entry.get("id", ""),
                entry.get("name", ""),
                entry.get("category", ""),
                "[green]available[/green]"
                if status_val == "available"
                else f"[dim]{status_val}[/dim]",
                entry.get("configuration_preset_kind") or "[dim]-[/dim]",
                ", ".join(entry.get("configuration_preset_names") or []) or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list blueprints.", details={"error": str(e)}
        )
