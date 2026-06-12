# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Update model metadata."""

import json
from typing import Any

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
async def update_model(
    ctx: typer.Context,
    model_id: Annotated[str, typer.Argument(help="Model name or ID")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description")
    ] = None,
    labels_json: Annotated[str | None, typer.Option("--labels", help="Labels as JSON")] = None,
):
    """Update model metadata.

    Examples:
        v8x cluster model-registry update gemma-4b -c my-cluster -d "Updated desc"
    """
    console = ctx.obj.console
    body: dict[str, Any] = {}
    if description is not None:
        body["description"] = description
    if labels_json:
        body["labels"] = json.loads(labels_json)
    if not body:
        console.print("[yellow]Nothing to update[/yellow]")
        return

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model/{model_id}"

        async with get_http_client() as client:
            response = await client.patch(url, json=body, headers=get_auth_headers(ctx))

        if response.status_code == 200:
            data = response.json()
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(f"[green]✓[/green] Model '{model_id}' updated")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to update model.", details={"error": str(e)}
        )
