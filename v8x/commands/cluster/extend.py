# Copyright (C) 2026 Vantage Compute Corporation
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
"""Extend a Vantage cluster with bare-metal compute nodes via Juju."""

import logging
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.commands.cluster.namespace._helpers import get_vdeployer_web_url
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

logger = logging.getLogger(__name__)


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def extend_cluster(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Argument(help="Name of the cluster to extend with bare-metal compute"),
    ],
    slurm_cluster: Annotated[
        str,
        typer.Option(
            "--slurm-cluster",
            "-s",
            help="Name of the Slurm cluster in vdeployer to connect to (default: uses first available)",
        ),
    ] = "",
    num_workers: Annotated[
        int,
        typer.Option(
            "--num-workers",
            "-n",
            help="Number of bare-metal compute nodes to deploy",
        ),
    ] = 1,
    cloud_account_id: Annotated[
        Optional[int],
        typer.Option(
            "--cloud-account-id",
            "-a",
            help="Cloud account ID with LXD credentials (auto-detected from cluster if omitted)",
        ),
    ] = None,
    vdeployer_url: Annotated[
        Optional[str],
        typer.Option(
            "--vdeployer-url",
            help="Override vdeployer-web URL (auto-derived from cluster if omitted)",
        ),
    ] = None,
    settings_file: Annotated[
        Optional[Path],
        typer.Option(
            "--settings-file",
            help="Path to YAML file with LXD connection settings",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
):
    """Extend a Vantage cluster with bare-metal compute nodes.

    Deploys vantage-slurmctld-proxy and vantage-slurmd charms on LXD machines
    via Juju, connecting them to the K8s-based Slurm controller. The connection
    details (slurmctld IP, auth key, TLS certs) are fetched automatically from
    the vdeployer-web API.

    Requires a cloud account with LXD credentials (lxd_server_url, lxd_client_cert,
    lxd_client_key).

    Examples:
        Extend a cluster with 3 bare-metal compute nodes:
        $ v8x cluster extend mycluster --slurm-cluster default -n 3 --cloud-account-id 16

        Extend using auto-detected cloud account:
        $ v8x cluster extend mycluster --slurm-cluster default
    """
    console = ctx.obj.console
    settings = ctx.obj.settings
    verbose = getattr(ctx.obj, "verbose", False)

    # 1. Get the cluster from the API
    console.print(f"[dim]Looking up cluster '{cluster_name}'...[/dim]")
    cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
    if not cluster:
        raise Abort(
            f"Cluster '{cluster_name}' not found.",
            subject="Cluster Not Found",
        )

    # 2. Resolve cloud account for LXD credentials
    if cloud_account_id is None:
        cloud_account_id_raw = cluster.cloud_account_id
        if not cloud_account_id_raw:
            raise Abort(
                "Cluster has no cloud account. Use --cloud-account-id to specify one.",
                subject="Missing Cloud Account",
            )
        cloud_account_id = int(cloud_account_id_raw)

    cloud_account = await cloud_account_sdk.get(ctx, cloud_account_id)
    if not cloud_account:
        raise Abort(
            f"Cloud account {cloud_account_id} not found.",
            subject="Cloud Account Not Found",
        )

    cloud_account_attributes = cloud_account.attributes or {}
    required_lxd_fields = ["lxd_server_url", "lxd_client_cert", "lxd_client_key"]
    missing = [f for f in required_lxd_fields if not cloud_account_attributes.get(f)]
    if missing:
        raise Abort(
            f"Cloud account is missing LXD credentials: {', '.join(missing)}.\n"
            "Ensure the cloud account was created with LXD connection details.",
            subject="Missing LXD Credentials",
        )

    # Load additional settings from file if provided
    if settings_file:
        import yaml

        with open(settings_file) as f:
            file_settings = yaml.safe_load(f) or {}
        # Merge file settings into cloud account attributes
        cloud_account_attributes.update(file_settings)

    # 3. Determine vdeployer-web URL
    if not vdeployer_url:
        vdeployer_url = get_vdeployer_web_url(cluster.client_id, settings.vantage_url)
    console.print(f"[dim]vdeployer-web: {vdeployer_url}[/dim]")

    # 4. If no slurm cluster name given, try to list and use the first one
    if not slurm_cluster:
        console.print("[dim]No --slurm-cluster specified, listing available clusters...[/dim]")
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                resp = await http_client.get(f"{vdeployer_url}/slurm-cluster")
                resp.raise_for_status()
                clusters_data = resp.json()

            cluster_list = clusters_data.get("clusters", [])
            if not cluster_list:
                raise Abort(
                    "No Slurm clusters found in vdeployer. Deploy a Slurm cluster first.",
                    subject="No Slurm Clusters",
                )

            slurm_cluster = cluster_list[0]["name"]
            console.print(f"[dim]Using Slurm cluster: {slurm_cluster}[/dim]")
        except httpx.HTTPError as e:
            raise Abort(
                f"Failed to list Slurm clusters from vdeployer-web: {e}",
                subject="API Error",
            )

    # 5. Set up ctx.obj for the juju_ext app
    ctx.obj.cloud_config_metadata = cloud_account_attributes
    ctx.obj.vdeployer_web_url = vdeployer_url
    ctx.obj.slurm_cluster_name = slurm_cluster
    ctx.obj.app_config = f"num_workers={num_workers}"

    # 6. Look up and invoke the juju-ext extension app
    from v8x.deployment_apps import deployment_app_sdk

    app = deployment_app_sdk.get("juju-ext", cloud="lxd")
    if app is None:
        raise Abort(
            "juju-ext extension app not found. Ensure v8x is installed correctly.",
            subject="Extension Not Found",
        )

    if not app.module or not hasattr(app.module, "create"):
        raise Abort(
            "juju-ext extension app does not support deployment.",
            subject="Invalid Extension",
        )

    console.print(
        f"\n[bold blue]Extending cluster '{cluster_name}' with {num_workers} "
        f"bare-metal compute node(s)...[/bold blue]\n"
    )

    result = await app.module.create(ctx, cluster, verbose=verbose)

    if isinstance(result, typer.Exit) and result.exit_code != 0:
        raise Abort(
            "Cluster extension failed. Check the output above for details.",
            subject="Extension Failed",
        )
