# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List NIM deployments."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nim_deployment import nim_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_nims(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List NIM deployments.

    Examples:
        v8x cluster nim list -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await nim_deployment_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        items = response.json()
        if not isinstance(items, list):
            items = items.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No NIM deployments found")
            return

        from rich.table import Table

        table = Table(title=f"NIM Deployments on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Model")
        table.add_column("Version")
        table.add_column("Ingress")
        table.add_column("Ready")
        table.add_column("URL")

        for dep in items:
            ing = dep.get("ingress", {}) or {}
            ingress_label = ing.get("type", "")
            if ingress_label == "public" and ing.get("auth"):
                ingress_label = f"{ingress_label}/{ing['auth']}"
            table.add_row(
                dep.get("name", ""),
                dep.get("catalog_id", ""),
                dep.get("version", ""),
                ingress_label or "[dim]-[/dim]",
                "[green]yes[/green]" if dep.get("ready") else "[yellow]no[/yellow]",
                (dep.get("url", "") or "")[:50] or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NIM deployments.", details={"error": str(e)}
        )
