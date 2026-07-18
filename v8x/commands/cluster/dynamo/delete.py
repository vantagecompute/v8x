# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Delete Dynamo deployment."""

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
async def delete_dynamo(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Deployment name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Delete a Dynamo deployment (DGDR + generated DGD).

    Examples:
        v8x cluster dynamo delete my-qwen -c my-cluster
    """
    console = ctx.obj.console
    if not force and not typer.confirm(f"Delete Dynamo deployment '{name}'?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    try:
        response = await dynamo_deployment_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Dynamo deployment '{name}' deleted")
        elif response.status_code == 404:
            console.print(f"[yellow]Dynamo deployment '{name}' not found[/yellow]")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to delete Dynamo deployment.", details={"error": str(e)}
        )
