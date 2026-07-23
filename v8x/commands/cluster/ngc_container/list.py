# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List NGC containers."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nvidia_catalogs import ngc_container_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_ngc_containers(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    purpose: Annotated[
        str | None,
        typer.Option("--purpose", "-p", help="Filter: training, workspace, serving"),
    ] = None,
):
    """List curated NGC framework containers.

    Examples:
        v8x cluster ngc-container list -c my-cluster --purpose training
    """
    console = ctx.obj.console
    try:
        response = await ngc_container_sdk.list(ctx, cluster_name=cluster_name, purpose=purpose)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        items = data.get("entries", []) if isinstance(data, dict) else data

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No NGC containers found")
            return

        from rich.table import Table

        table = Table(title=f"NGC Containers on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Display Name")
        table.add_column("Repository")
        table.add_column("Tag")
        table.add_column("Purposes")
        table.add_column("NVAIE")

        for entry in items:
            table.add_row(
                entry.get("name", ""),
                entry.get("display_name", ""),
                entry.get("repository", ""),
                entry.get("recommended_tag", ""),
                ", ".join(entry.get("purposes") or []),
                "[yellow]yes[/yellow]"
                if entry.get("nvidia_ai_enterprise_required")
                else "[dim]no[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NGC containers.", details={"error": str(e)}
        )
