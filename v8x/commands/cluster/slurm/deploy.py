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
"""Deploy Slurm cluster command — triggers vdeployer-web deployment."""

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
async def deploy_slurm_cluster(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name of the Slurm cluster to deploy"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    control_node_group: Annotated[
        str,
        typer.Option(
            "--control-node-group",
            help="Node group name for the slurmctld controller",
        ),
    ],
    partition: Annotated[
        list[str],
        typer.Option(
            "--partition",
            help="Partition spec as 'name:node_group' or 'name:node_group:default'. Repeatable.",
        ),
    ],
    exposed: Annotated[
        bool,
        typer.Option(
            "--exposed/--no-exposed",
            help="Expose SLURM services via NodePort",
        ),
    ] = False,
    tls_enabled: Annotated[
        bool,
        typer.Option(
            "--tls/--no-tls",
            help="Enable TLS for internal SLURM communication",
        ),
    ] = True,
    profiling: Annotated[
        bool,
        typer.Option(
            "--profiling/--no-profiling",
            help="Enable InfluxDB for SLURM job profiling",
        ),
    ] = True,
    bridge: Annotated[
        bool,
        typer.Option(
            "--bridge/--no-bridge",
            help="Enable slurm-bridge for K8s scheduler integration",
        ),
    ] = True,
):
    r"""Deploy a Slurm cluster via vdeployer-web.

    This command sends a POST to vdeployer-web's /slurm-cluster endpoint to
    trigger the actual Slurm deployment (operator, slurmdbd, slurmctld, etc.).
    The Slurm cluster must first be registered with 'v8x cluster slurm create'.

    This is a background operation — use 'v8x cluster slurm get' to check status.

    Examples:
        v8x cluster slurm deploy hpc-prod -c my-cluster \\
            --control-node-group slurm-admin \\
            --partition cpu:slurm-compute:default \\
            --exposed --profiling
    """
    console = ctx.obj.console

    try:
        console.print(f"[dim]Deploying Slurm cluster '{name}' via vdeployer-web...[/dim]")
        result = await slurm_sdk.deploy(
            ctx,
            cluster_name=cluster_name,
            name=name,
            control_node_group=control_node_group,
            partition_specs=partition,
            exposed=exposed,
            tls_enabled=tls_enabled,
            profiling=profiling,
            bridge=bridge,
        )
        response = result.response

        if response.status_code == 200:
            data = response.json() or {}
            console.print(
                f"[green]\u2713[/green] {data.get('message', f'Slurm cluster {name} deployment started')}"
            )
        elif response.status_code == 409:
            data = response.json() or {}
            console.print(
                f"[yellow]Warning:[/yellow] {data.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to deploy Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
