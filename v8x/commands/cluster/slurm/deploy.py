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

    # Get the slurm cluster's OIDC credentials.
    # The cluster must already exist (created by 'v8x cluster slurm create').
    slurm_client_id = await cluster_sdk.get_slurm_cluster_client_id(ctx, name, cluster_name)
    if not slurm_client_id:
        raise Abort(
            f"Slurm cluster '{name}' not found under parent '{cluster_name}'. "
            "Run 'v8x cluster slurm create' first.",
            subject="Slurm Cluster Not Found",
        )
    slurm_client_secret = await cluster_sdk.get_cluster_client_secret(
        ctx=ctx, client_id=slurm_client_id
    )
    if not slurm_client_secret:
        raise Abort(
            f"Failed to fetch client secret for Slurm cluster '{name}' (clientId: {slurm_client_id})",
            subject="Slurm Cluster Secret Not Found",
        )

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        slurm_sssd_binder_password = cluster.sssd_binder_password
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
        }

        if slurm_client_id:
            request_data["client_id"] = slurm_client_id
        if slurm_client_secret:
            request_data["client_secret"] = slurm_client_secret
        if slurm_sssd_binder_password:
            request_data["sssd_binder_password"] = slurm_sssd_binder_password

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
