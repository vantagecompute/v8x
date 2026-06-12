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
"""Update Slurm cluster command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.slurm import slurm_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def update_slurm_cluster(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the Slurm cluster to update"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    exposed: Annotated[
        bool | None,
        typer.Option(
            "--exposed/--no-exposed",
            help="Expose SLURM services via NodePort",
        ),
    ] = None,
    tls_enabled: Annotated[
        bool | None,
        typer.Option(
            "--tls/--no-tls",
            help="Enable TLS for internal SLURM communication",
        ),
    ] = None,
    profiling: Annotated[
        bool | None,
        typer.Option(
            "--profiling/--no-profiling",
            help="Enable InfluxDB for SLURM job profiling",
        ),
    ] = None,
    bridge: Annotated[
        bool | None,
        typer.Option(
            "--bridge/--no-bridge",
            help="Enable slurm-bridge for K8s scheduler integration",
        ),
    ] = None,
):
    """Update settings for an existing Slurm cluster.

    Only provided flags are changed — omitted flags keep their current values.
    This is a background operation — the cluster will be redeployed asynchronously.

    Examples:
        v8x cluster slurm update hpc-prod --cluster my-cluster --profiling
        v8x cluster slurm update ml-dev -c my-cluster --no-bridge
        v8x cluster slurm update research -c my-cluster --exposed --no-tls
    """
    console = ctx.obj.console

    try:
        console.print(f"[dim]Updating Slurm cluster '{name}' on '{cluster_name}'...[/dim]")

        response = await slurm_sdk.update(
            ctx,
            cluster_name=cluster_name,
            name=name,
            exposed=exposed,
            tls_enabled=tls_enabled,
            profiling=profiling,
            bridge=bridge,
        )

        if response.status_code == 200:
            payload = response.json() or {}
            console.print(
                f"[green]✓[/green] {payload.get('message', f'Slurm cluster {name} update started')}"
            )
        elif response.status_code == 404:
            payload = response.json() or {}
            console.print(
                f"[yellow]Not found:[/yellow] {payload.get('detail', 'Cluster not found')}"
            )
        elif response.status_code == 409:
            payload = response.json() or {}
            console.print(
                f"[yellow]Warning:[/yellow] {payload.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to update Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
