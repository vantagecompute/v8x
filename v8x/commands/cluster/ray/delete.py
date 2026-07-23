# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Delete Ray job."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.ray_job import ray_job_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_ray_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="RayJob name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Delete a Ray job (KubeRay tears down the associated RayCluster).

    Examples:
        v8x cluster ray delete train-1 -c my-cluster
    """
    console = ctx.obj.console
    if not force and not typer.confirm(f"Delete Ray job '{name}'?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    try:
        response = await ray_job_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Ray job '{name}' deleted")
        elif response.status_code == 404:
            console.print(f"[yellow]Ray job '{name}' not found[/yellow]")
        else:
            console.print(f"[red]Error:[/red] {response.status_code}: {response.text}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to delete Ray job.", details={"error": str(e)}
        )
