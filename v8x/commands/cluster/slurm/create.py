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
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import (
    build_vdeployer_settings,
    get_auth_headers,
    get_cluster_with_creds,
    get_http_client,
    get_vdeployer_web_url,
)


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

    # Parse partition specs
    partitions: list[dict[str, object]] = []
    for spec in partition:
        parts = spec.split(":")
        if len(parts) < 2:
            raise Abort(
                f"Invalid partition spec '{spec}'. Use 'name:node_group' or 'name:node_group:default'.",
                subject="Invalid Input",
            )
        p: dict[str, object] = {"name": parts[0], "node_group": parts[1]}
        if len(parts) >= 3 and parts[2] == "default":
            p["default"] = True
        partitions.append(p)

    # Step 1: Register the Slurm cluster via API
    console.print(
        f"[dim]Registering Slurm cluster '{name}' in K8s cluster '{cluster_name}'...[/dim]"
    )

    slurm_record = await cluster_sdk.create_slurm_cluster(
        ctx,
        name=name,
        parent_cluster_name=cluster_name,
    )
    slurm_client_id = slurm_record.get("clientId")
    slurm_client_secret = slurm_record.get("clientSecret")

    if not slurm_client_id or not slurm_client_secret:
        raise Abort(
            f"Failed to get credentials for Slurm cluster '{name}'. "
            f"clientId={'present' if slurm_client_id else 'missing'}, "
            f"clientSecret={'present' if slurm_client_secret else 'missing'}",
            subject="Slurm Cluster Credentials Missing",
        )

    console.print(f"[green]\u2713[/green] Slurm cluster [green]'{name}'[/green] registered")
    console.print(f"  Client ID: {slurm_client_id}")
    console.print(f"  Client Secret: {slurm_client_secret[:20]}...")

    # Step 2: Deploy via vdeployer-web
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        vdeployer_settings = await build_vdeployer_settings(ctx, cluster)

        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        url = f"{vdeployer_url}/slurm-cluster"

        request_data = {
            "name": name,
            "settings": vdeployer_settings,
            "control_node_group": control_node_group,
            "partitions": partitions,
            "exposed": exposed,
            "tls_enabled": tls_enabled,
            "profiling_enabled": profiling,
            "bridge_enabled": bridge,
            "client_id": slurm_client_id,
            "client_secret": slurm_client_secret,
        }
        # Only include the pinned LB IPs in the request when they were
        # supplied — vdeployer treats them as "required if exposed=True"
        # and their absence is a clear server-side validation error.
        if slurmctld_lb_ip:
            request_data["slurmctld_lb_ip"] = slurmctld_lb_ip
        if slurmdbd_lb_ip:
            request_data["slurmdbd_lb_ip"] = slurmdbd_lb_ip
        if slurmrestd_lb_ip:
            request_data["slurmrestd_lb_ip"] = slurmrestd_lb_ip
        if influxdb_lb_ip:
            request_data["influxdb_lb_ip"] = influxdb_lb_ip

        console.print(f"[dim]Deploying Slurm cluster '{name}' via vdeployer-web...[/dim]")

        async with get_http_client() as client:
            response = await client.post(
                url,
                json=request_data,
                headers=get_auth_headers(ctx),
            )

        if response.status_code == 200:
            result = response.json()
            console.print(
                f"[green]\u2713[/green] {result.get('message', f'Slurm cluster {name} deployment started')}"
            )
        elif response.status_code == 409:
            result = response.json()
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
            error_message=f"Failed to deploy Slurm cluster '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
