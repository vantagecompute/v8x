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
"""Create and deploy a Slurm cluster command."""

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
async def create_slurm_cluster(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name for the Slurm cluster (DNS-safe, e.g. 'hpc-prod')"),
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
    slurmctld_lb_ip: Annotated[
        str | None,
        typer.Option(
            "--slurmctld-lb-ip",
            help=(
                "Optionally pin the MetalLB LoadBalancer IP for slurmctld. "
                "When unset, MetalLB allocates from its pool. Pin only when "
                "off-cluster clients need a stable address (e.g. for "
                "/etc/hosts mapping). Example: 192.168.8.221"
            ),
        ),
    ] = None,
    slurmdbd_lb_ip: Annotated[
        str | None,
        typer.Option(
            "--slurmdbd-lb-ip",
            help="Optionally pin the MetalLB LoadBalancer IP for slurmdbd (auto-allocated when unset).",
        ),
    ] = None,
    slurmrestd_lb_ip: Annotated[
        str | None,
        typer.Option(
            "--slurmrestd-lb-ip",
            help="Optionally pin the MetalLB LoadBalancer IP for slurmrestd (auto-allocated when unset).",
        ),
    ] = None,
    influxdb_lb_ip: Annotated[
        str | None,
        typer.Option(
            "--influxdb-lb-ip",
            help=(
                "Optionally pin the MetalLB LoadBalancer IP for InfluxDB. "
                "When unset, MetalLB allocates from its pool. Pin when "
                "off-cluster slurmd pushes job profiling metrics here AND "
                "needs the IP in the InfluxDB TLS cert SAN."
            ),
        ),
    ] = None,
):
    r"""Create and deploy a Slurm cluster within a Vantage K8s cluster.

    Registers the Slurm cluster via the API (creates Keycloak client and DB record),
    then triggers deployment via vdeployer-web (operator, slurmdbd, slurmctld, etc.).

    This is a background operation — use 'v8x cluster slurm get' to check status.

    Examples:
        v8x cluster slurm create hpc-prod -c my-cluster \\
            --control-node-group slurm-admin \\
            --partition cpu:slurm-compute:default \\
            --exposed --profiling \\
            --slurmctld-lb-ip 192.168.8.221 \\
            --slurmdbd-lb-ip 192.168.8.220 \\
            --slurmrestd-lb-ip 192.168.8.222
    """
    console = ctx.obj.console

    try:
        result = await slurm_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            control_node_group=control_node_group,
            partition_specs=partition,
            exposed=exposed,
            tls_enabled=tls_enabled,
            profiling=profiling,
            bridge=bridge,
            slurmctld_lb_ip=slurmctld_lb_ip,
            slurmdbd_lb_ip=slurmdbd_lb_ip,
            slurmrestd_lb_ip=slurmrestd_lb_ip,
            influxdb_lb_ip=influxdb_lb_ip,
        )
        slurm_client_id = result.registration.get("clientId")
        slurm_client_secret = result.registration.get("clientSecret")
        console.print(f"[green]\u2713[/green] Slurm cluster [green]'{name}'[/green] registered")
        console.print(f"  Client ID: {slurm_client_id}")
        if slurm_client_secret:
            console.print(f"  Client Secret: {slurm_client_secret[:20]}...")
        console.print(f"[dim]Deploying Slurm cluster '{name}' via vdeployer-web...[/dim]")

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
