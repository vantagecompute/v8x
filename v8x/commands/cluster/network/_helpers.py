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

"""Helpers for cluster network commands."""

import json
from typing import Any

from pydantic import ValidationError
from rich.panel import Panel
from rich.table import Table
from vantage_sdk.cluster.network import Ipam, IpamType, Network, NetworkType, NetworkUpdate
from vantage_sdk.exceptions import Abort

SUPPORTED_IPAM_VALUES = {"nv-ipam"}


def parse_network_type(value: str) -> NetworkType:
    """Parse a network type option."""
    try:
        return NetworkType(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in NetworkType)
        raise Abort(
            f"Invalid network type '{value}'. Valid values: {allowed}.",
            subject="Invalid Input",
        ) from exc


def parse_ipam_type(value: str) -> IpamType:
    """Parse an IPAM type option."""
    if value not in SUPPORTED_IPAM_VALUES:
        allowed = ", ".join(sorted(SUPPORTED_IPAM_VALUES))
        raise Abort(
            f"Invalid IPAM type '{value}'. Valid values: {allowed}.",
            subject="Invalid Input",
        )
    try:
        return IpamType(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in IpamType)
        raise Abort(
            f"Invalid IPAM type '{value}'. Valid values: {allowed}.",
            subject="Invalid Input",
        ) from exc


def parse_routes(route_values: list[str] | None) -> list[dict[str, Any]]:
    """Parse repeated route JSON option values."""
    routes: list[dict[str, Any]] = []
    for route_value in route_values or []:
        try:
            route = json.loads(route_value)
        except json.JSONDecodeError as exc:
            raise Abort(
                f"Invalid JSON for --route: {exc}",
                subject="Invalid Input",
            ) from exc
        if not isinstance(route, dict):
            raise Abort("Each --route value must be a JSON object.", subject="Invalid Input")
        routes.append(route)
    return routes


def build_ipam(
    *,
    ipam_type: str,
    ip_range: str | None,
    gateway: str | None,
    exclude: list[str] | None,
    route: list[str] | None,
    per_node_block_size: int | None,
) -> Ipam:
    """Build an SDK IPAM model from CLI option values."""
    try:
        return Ipam(
            ipam_type=parse_ipam_type(ipam_type),
            ip_range=ip_range or "",
            gateway=gateway or "",
            exclude=exclude or [],
            routes=parse_routes(route),
            per_node_block_size=per_node_block_size or 0,
        )
    except ValidationError as exc:
        raise Abort(str(exc), subject="Invalid Network") from exc


def build_network(
    *,
    name: str,
    network_type: str,
    iface_name: str | None,
    bridge: str | None,
    vlan: int | None,
    mtu: int,
    ipam_type: str,
    ip_range: str | None,
    gateway: str | None,
    exclude: list[str] | None,
    route: list[str] | None,
    per_node_block_size: int | None,
) -> Network:
    """Build a full SDK network model from CLI option values."""
    try:
        return Network(
            name=name,
            network_type=parse_network_type(network_type),
            iface_name=iface_name or "",
            bridge=bridge or "",
            vlan=vlan,
            mtu=mtu,
            ipam=build_ipam(
                ipam_type=ipam_type,
                ip_range=ip_range,
                gateway=gateway,
                exclude=exclude,
                route=route,
                per_node_block_size=per_node_block_size,
            ),
        )
    except ValidationError as exc:
        raise Abort(str(exc), subject="Invalid Network") from exc


def build_network_update(
    *,
    network_type: str | None,
    iface_name: str | None,
    bridge: str | None,
    vlan: int | None,
    mtu: int | None,
    ipam_type: str | None,
    ip_range: str | None,
    gateway: str | None,
    exclude: list[str] | None,
    route: list[str] | None,
    per_node_block_size: int | None,
) -> NetworkUpdate:
    """Build a partial SDK network update model from CLI option values."""
    patch: dict[str, Any] = {}
    if network_type is not None:
        patch["network_type"] = parse_network_type(network_type)
    if iface_name is not None:
        patch["iface_name"] = iface_name
    if bridge is not None:
        patch["bridge"] = bridge
    if vlan is not None:
        patch["vlan"] = vlan
    if mtu is not None:
        patch["mtu"] = mtu

    has_ipam_change = any(
        value is not None
        for value in (ipam_type, ip_range, gateway, exclude, route, per_node_block_size)
    )
    if has_ipam_change:
        patch["ipam"] = build_ipam(
            ipam_type=ipam_type or IpamType.NV_IPAM.value,
            ip_range=ip_range,
            gateway=gateway,
            exclude=exclude,
            route=route,
            per_node_block_size=per_node_block_size,
        )

    if not patch:
        raise Abort("No network updates provided.", subject="Missing Input")

    try:
        return NetworkUpdate(**patch)
    except ValidationError as exc:
        raise Abort(str(exc), subject="Invalid Network") from exc


def network_items(data: Any) -> list[dict[str, Any]]:
    """Normalize network list responses."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("items", data.get("networks", []))
        return items if isinstance(items, list) else []
    return []


def display_value(value: Any) -> str:
    """Format an optional value for rich output."""
    if value in (None, "", [], {}):
        return "[dim]-[/dim]"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "[dim]-[/dim]"
    return str(value)


def render_ipam_summary(network: dict[str, Any]) -> str:
    """Format a compact IPAM summary for tables."""
    ipam = network.get("ipam") or {}
    if not isinstance(ipam, dict):
        return "[dim]-[/dim]"
    ip_range = ipam.get("ip_range") or ipam.get("range") or ""
    gateway = ipam.get("gateway") or ""
    if ip_range and gateway:
        return f"{ip_range} via {gateway}"
    return display_value(ip_range or gateway)


def print_network_table(
    console: Any, networks: list[dict[str, Any]], *, cluster_name: str
) -> None:
    """Render networks as a table."""
    table = Table(title=f"Networks on '{cluster_name}'")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Interface")
    table.add_column("Bridge")
    table.add_column("VLAN")
    table.add_column("MTU")
    table.add_column("IPAM")

    for network in networks:
        table.add_row(
            display_value(network.get("name")),
            display_value(network.get("network_type", network.get("type"))),
            display_value(network.get("iface_name")),
            display_value(network.get("bridge")),
            display_value(network.get("vlan")),
            display_value(network.get("mtu")),
            render_ipam_summary(network),
        )

    console.print(table)


def print_network_detail(console: Any, network: dict[str, Any], *, title: str) -> None:
    """Render a single network as a panel."""
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Name", display_value(network.get("name")))
    table.add_row("Type", display_value(network.get("network_type", network.get("type"))))
    table.add_row("Mode", display_value(network.get("mode")))
    table.add_row("Interface", display_value(network.get("iface_name")))
    table.add_row("Bridge", display_value(network.get("bridge")))
    table.add_row("VLAN", display_value(network.get("vlan")))
    table.add_row("MTU", display_value(network.get("mtu")))

    ipam = network.get("ipam") or {}
    if isinstance(ipam, dict):
        table.add_row("IPAM Type", display_value(ipam.get("ipam_type", ipam.get("type"))))
        table.add_row("IP Range", display_value(ipam.get("ip_range", ipam.get("range"))))
        table.add_row("Gateway", display_value(ipam.get("gateway")))
        table.add_row("Exclude", display_value(ipam.get("exclude")))
        table.add_row("Routes", display_value(ipam.get("routes")))
        table.add_row("Per-node block", display_value(ipam.get("per_node_block_size")))

    console.print(Panel(table, title=title))
