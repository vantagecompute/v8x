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

"""Update cluster network command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.network import network_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import build_network_update, print_network_detail


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def update_network(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
    network_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="CNI type: macvlan, ipvlan, host-device, or sriov"),
    ] = None,
    iface_name: Annotated[
        str | None,
        typer.Option("--iface-name", help="Interface name inside pods"),
    ] = None,
    bridge: Annotated[
        str | None,
        typer.Option("--bridge", help="Host interface or bridge to attach"),
    ] = None,
    vlan: Annotated[int | None, typer.Option("--vlan", help="VLAN ID")] = None,
    mtu: Annotated[int | None, typer.Option("--mtu", help="MTU")] = None,
    ipam_type: Annotated[
        str | None,
        typer.Option("--ipam-type", help="IPAM type: nv-ipam"),
    ] = None,
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
    """Update a Multus network on a Vantage cluster.

    Examples:
        v8x cluster network update data-net -c my-cluster --mtu 9000
        v8x cluster network update data-net -c my-cluster --ip-range 10.20.0.0/24 --gateway 10.20.0.1
        v8x cluster network update vlan10 -c my-cluster --ip-range 192.168.10.0/24
    """
    console = ctx.obj.console
    patch = build_network_update(
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
        response = await network_sdk.update(
            ctx,
            cluster_name=cluster_name,
            name=name,
            patch=patch,
        )

        if response.status_code in (200, 202):
            data = response.json() or {"name": name, "updated": True}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
                return
            console.print(f"[green]✓[/green] Network '{name}' updated")
            if isinstance(data, dict):
                print_network_detail(console, data, title=f"Network: {name}")
            return

        if response.status_code == 404:
            console.print(f"[yellow]Network '{name}' not found[/yellow]")
            return

        raise Abort(f"Failed to update network: {response.text}", subject="API Error")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to update network '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
