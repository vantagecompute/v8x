# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get blueprint."""

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
async def get_blueprint(
    ctx: typer.Context,
    blueprint_id: Annotated[str, typer.Argument(help="Blueprint ID (e.g. nvidia-rag)")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get one curated NVIDIA AI Blueprint.

    Examples:
        v8x cluster blueprint get nvidia-rag -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await blueprint_sdk.get(
            ctx, cluster_name=cluster_name, blueprint_id=blueprint_id
        )

        if response.status_code == 404:
            console.print(f"[yellow]Blueprint '{blueprint_id}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        console.print(
            f"[bold]{data.get('name', blueprint_id)}[/bold] ({data.get('id', blueprint_id)})"
        )
        console.print(f"  Category:    {data.get('category', 'N/A')}")
        console.print(f"  Status:      {data.get('status', 'N/A')}")
        console.print(f"  Preset Kind: {data.get('configuration_preset_kind') or 'N/A'}")
        presets = ", ".join(data.get("configuration_preset_names") or []) or "N/A"
        console.print(f"  Presets:     {presets}")
        console.print(f"  Docs:        {data.get('docs_url') or 'N/A'}")
        console.print(f"  Description: {data.get('description', 'N/A')}")
        components = data.get("components") or []
        if components:
            console.print("  Components:")
            for comp in components:
                console.print(
                    f"    {comp.get('role', '')}: {comp.get('catalog_id', '')} "
                    f"([dim]{comp.get('catalog', '')}[/dim])"
                )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get blueprint.", details={"error": str(e)}
        )
