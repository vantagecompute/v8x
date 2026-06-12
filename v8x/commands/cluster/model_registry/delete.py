# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Delete model version."""

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
async def delete_model_version(
    ctx: typer.Context,
    model_version_id: Annotated[str, typer.Argument(help="Model version ID to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Delete a model version.

    Examples:
        v8x cluster model-registry delete <version-id> -c my-cluster
    """
    console = ctx.obj.console
    if not force and not typer.confirm(f"Delete model version '{model_version_id}'?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model/versions/{model_version_id}"

        async with get_http_client() as client:
            response = await client.delete(url, headers=get_auth_headers(ctx))

        if response.status_code == 200:
            console.print(f"[green]✓[/green] Model version '{model_version_id}' deleted")
        elif response.status_code == 404:
            console.print("[yellow]Model version not found[/yellow]")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to delete.", details={"error": str(e)}
        )
