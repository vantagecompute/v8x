# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Browse the NIM catalog."""

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
async def catalog_nim(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    task: Annotated[
        str | None, typer.Option("--task", help="Filter by task (e.g. text-generation)")
    ] = None,
    publisher: Annotated[
        str | None, typer.Option("--publisher", help="Filter by publisher (e.g. meta)")
    ] = None,
    query: Annotated[str | None, typer.Option("--query", "-q", help="Free-text filter")] = None,
):
    """List NIM catalog entries.

    Examples:
        v8x cluster nim catalog -c my-cluster --task text-generation
    """
    console = ctx.obj.console
    try:
        response = await nim_deployment_sdk.catalog(
            ctx, cluster_name=cluster_name, task=task, publisher=publisher, q=query
        )

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        items = data if isinstance(data, list) else data.get("entries", [])

        if ctx.obj.json_output:
            print(json.dumps(items, default=str))
            return

        if not items:
            console.print("No catalog entries found")
            return

        from rich.table import Table

        table = Table(title=f"NIM Catalog on '{cluster_name}'")
        table.add_column("Id", style="bold")
        table.add_column("Publisher")
        table.add_column("Tasks")
        table.add_column("Recommended Tag")
        table.add_column("Status")

        for entry in items:
            container = entry.get("container", {}) or {}
            table.add_row(
                entry.get("id", ""),
                entry.get("publisher", "") or "[dim]-[/dim]",
                ", ".join(entry.get("tasks", []) or []) or "[dim]-[/dim]",
                container.get("recommended_tag", "") or "[dim]-[/dim]",
                entry.get("status", "") or "[dim]-[/dim]",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NIM catalog.", details={"error": str(e)}
        )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def versions_nim(
    ctx: typer.Context,
    catalog_id: Annotated[str, typer.Argument(help="Catalog id, e.g. meta/llama-3.1-8b-instruct")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """List approved/blocked versions for a NIM catalog entry.

    Examples:
        v8x cluster nim versions meta/llama-3.1-8b-instruct -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await nim_deployment_sdk.versions(
            ctx, cluster_name=cluster_name, catalog_id=catalog_id
        )

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        versions = data.get("versions", []) if isinstance(data, dict) else data
        if not versions:
            console.print(f"No versions found for '{catalog_id}'")
            return

        recommended = data.get("recommended_tag") if isinstance(data, dict) else None

        from rich.table import Table

        table = Table(title=f"Versions for '{catalog_id}'")
        table.add_column("Tag", style="bold")
        table.add_column("Approved")
        table.add_column("Blocked")
        table.add_column("")

        for v in versions:
            tag = v.get("tag", "") if isinstance(v, dict) else str(v)
            approved = v.get("approved", False) if isinstance(v, dict) else False
            blocked = v.get("blocked", False) if isinstance(v, dict) else False
            table.add_row(
                tag,
                "[green]yes[/green]" if approved else "no",
                "[red]yes[/red]" if blocked else "no",
                "[cyan]recommended[/cyan]" if tag and tag == recommended else "",
            )
        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NIM versions.", details={"error": str(e)}
        )
