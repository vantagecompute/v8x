# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""List Dynamo deployments."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.dynamo_deployment import dynamo_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_dynamos(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List Dynamo deployments.

    Examples:
        v8x cluster dynamo list -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await dynamo_deployment_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        items = response.json()
        if not isinstance(items, list):
            items = items.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No Dynamo deployments found")
            return

        from rich.table import Table

        table = Table(title=f"Dynamo Deployments on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Model")
        table.add_column("Backend")
        table.add_column("Phase")
        table.add_column("DGD Ready")
        table.add_column("URL")

        for dep in items:
            table.add_row(
                dep.get("name", ""),
                dep.get("model", ""),
                dep.get("backend", ""),
                dep.get("phase", "") or "[dim]-[/dim]",
                "[green]yes[/green]" if dep.get("dgd_ready") else "[yellow]no[/yellow]",
                (dep.get("url", "") or "")[:50] or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list Dynamo deployments.", details={"error": str(e)}
        )
