# Copyright (C) 2025 Vantage Compute Corporation
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""Remove Kubeflow command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.application.kubeflow import kubeflow_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_kubeflow(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """Remove Kubeflow from a Vantage K8s cluster.

    This removes all Kubeflow components and namespaces. This is a background
    operation — use 'v8x cluster kubeflow get' to check status.

    Examples:
        v8x cluster kubeflow delete --cluster my-cluster
        v8x cluster kubeflow delete -c my-cluster --yes
    """
    console = ctx.obj.console

    if not yes:
        confirm = typer.confirm(f"Remove Kubeflow from '{cluster_name}'?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            return

    try:
        console.print(f"[dim]Removing Kubeflow from '{cluster_name}'...[/dim]")
        response = await kubeflow_sdk.delete(ctx, cluster_name=cluster_name)

        if response.status_code == 200:
            result = response.json() or {}
            console.print(
                f"[green]\u2713[/green] {result.get('message', 'Kubeflow removal started')}"
            )
        elif response.status_code == 409:
            result = response.json() or {}
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to remove Kubeflow from '{cluster_name}'.",
            details={"error": str(e)},
        )
