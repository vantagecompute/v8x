# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get NGC container."""

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
async def get_ngc_container(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Container name (e.g. nemo, pytorch)")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Get one curated NGC container.

    Examples:
        v8x cluster ngc-container get nemo -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await ngc_container_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            console.print(f"[yellow]NGC container '{name}' not found[/yellow]")
            return
        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        console.print(f"[bold]{data.get('display_name', name)}[/bold] ({data.get('name', name)})")
        console.print(f"  Registry:    {data.get('registry', 'N/A')}")
        console.print(f"  Repository:  {data.get('repository', 'N/A')}")
        console.print(f"  Tag:         {data.get('recommended_tag', 'N/A')}")
        console.print(f"  Purposes:    {', '.join(data.get('purposes') or []) or 'N/A'}")
        nvaie = "yes" if data.get("nvidia_ai_enterprise_required") else "no"
        console.print(f"  NVAIE:       {nvaie}")
        console.print(f"  Description: {data.get('description', 'N/A')}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get NGC container.", details={"error": str(e)}
        )
