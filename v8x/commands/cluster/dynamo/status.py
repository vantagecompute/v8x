# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Dynamo platform status."""

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
async def status_dynamo(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Show Dynamo platform status on a cluster.

    Examples:
        v8x cluster dynamo status -c my-cluster
    """
    console = ctx.obj.console
    try:
        response = await dynamo_deployment_sdk.status(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        deployed = data.get("deployed", False)
        state = "[green]deployed[/green]" if deployed else "[yellow]not deployed[/yellow]"
        console.print(f"Dynamo platform on '{cluster_name}': {state}")
        for key, value in data.items():
            if key == "deployed":
                continue
            console.print(f"  {key}: {value}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get Dynamo status.", details={"error": str(e)}
        )
