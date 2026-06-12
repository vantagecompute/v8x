# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create cluster network command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.network import network_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import build_network, print_network_detail


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_network(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
    network_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="CNI type: macvlan, ipvlan, host-device, or sriov",
        ),
    ] = "macvlan",
    iface_name: Annotated[
        str | None,
        typer.Option("--iface-name", help="Interface name inside pods"),
    ] = None,
    bridge: Annotated[
        str | None,
        typer.Option("--bridge", help="Host interface or bridge to attach"),
    ] = None,
    vlan: Annotated[int | None, typer.Option("--vlan", help="VLAN ID")] = None,
    mtu: Annotated[int, typer.Option("--mtu", help="MTU, or 0 for plugin default")] = 0,
    ipam_type: Annotated[
        str,
        typer.Option("--ipam-type", help="IPAM type: nv-ipam"),
    ] = "nv-ipam",
    ip_range: Annotated[
        str | None,
        typer.Option(
            "--ip-range",
            help="IPAM CIDR",
        ),
    ] = None,
    gateway: Annotated[str | None, typer.Option("--gateway", help="IPAM gateway IP")] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="CIDR to exclude from NV-IPAM"),
    ] = None,
    per_node_block_size: Annotated[
        int | None,
        typer.Option("--per-node-block-size", help="NV-IPAM IPPool addresses allocated per node"),
    ] = None,
    route: Annotated[
        list[str] | None,
        typer.Option("--route", help='Route JSON, e.g. \'{"dst":"0.0.0.0/0"}\''),
    ] = None,
):
    """Create a Multus network on a Vantage cluster.

    Attaches a secondary pod network using one of the supported CNI types
    (macvlan, ipvlan, or host-device) with NV-IPAM address management.
    Pods requesting the network get an additional interface with an IP
    allocated from the configured range.

    CNI types:

      macvlan     — virtual MACs on a parent interface (mode: bridge). Default.
      ipvlan      — shared MAC, isolated L2 (mode: l2). Needs --vlan or --bridge.
      host-device — moves an entire host interface into the pod namespace.
                    IPAM is optional (the device may carry its own addressing).

    Examples:
      # Basic macvlan with gateway:
      v8x cluster network create data-net my-cluster \
        --ip-range 10.20.0.0/24 --gateway 10.20.0.1

      # Macvlan on a specific bridge, excluding a reserved sub-range:
      v8x cluster network create mgmt-net my-cluster \
        --bridge br0 --ip-range 192.168.1.0/24 --gateway 192.168.1.1 \
        --exclude 192.168.1.0/28

      # Macvlan with multiple exclusions and custom MTU:
      v8x cluster network create storage-net my-cluster \
        --bridge br-stor --ip-range 10.50.0.0/16 \
        --exclude 10.50.0.0/24 --exclude 10.50.255.0/24 --mtu 9000

      # IPvlan on a VLAN trunk:
      v8x cluster network create vlan120 my-cluster \
        --network-type ipvlan --vlan 120 \
        --ip-range 10.120.0.0/24 --gateway 10.120.0.1

      # IPvlan with a per-node block size (controls NV-IPAM allocation granularity):
      v8x cluster network create hpc-net my-cluster \
        --network-type ipvlan --bridge bond0 --ip-range 10.80.0.0/20 \
        --per-node-block-size 64

      # Host-device passthrough (no IPAM — device has its own addressing):
      v8x cluster network create passthru my-cluster \
        --network-type host-device

      # Host-device with IPAM and a default route:
      v8x cluster network create wan-net my-cluster \
        --network-type host-device \
        --ip-range 203.0.113.0/28 --gateway 203.0.113.1 \
        --route '{"dst":"0.0.0.0/0"}'

      # Default route + specific subnet route:
      v8x cluster network create multi-route my-cluster \
        --ip-range 10.30.0.0/24 --gateway 10.30.0.1 \
        --route '{"dst":"0.0.0.0/0"}' \
        --route '{"dst":"172.16.0.0/12"}'

      # Route to a specific CIDR (e.g. storage network behind a different hop):
      v8x cluster network create stor-net my-cluster \
        --ip-range 10.40.0.0/24 --gateway 10.40.0.1 \
        --route '{"dst":"10.99.0.0/16"}'

      # Custom in-pod interface name:
      v8x cluster network create data-net my-cluster \
        --ip-range 10.20.0.0/24 --iface-name data0
    """
    console = ctx.obj.console
    network = build_network(
        name=name,
        network_type=network_type,
        iface_name=iface_name,
        bridge=bridge,
        vlan=vlan,
        mtu=mtu,
        ipam_type=ipam_type,
        ip_range=ip_range,
        gateway=gateway,
        exclude=exclude,
        route=route,
        per_node_block_size=per_node_block_size,
    )

    try:
        response = await network_sdk.create(ctx, cluster_name=cluster_name, network=network)

        if response.status_code in (200, 201):
            data = response.json() or network.model_dump()
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
                return
            console.print(f"[green]✓[/green] Network '{name}' created")
            if isinstance(data, dict):
                print_network_detail(console, data, title=f"Network: {name}")
            return

        if response.status_code == 409:
            console.print(f"[yellow]Network '{name}' already exists[/yellow]")
            return

        raise Abort(f"Failed to create network: {response.text}", subject="API Error")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create network '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
