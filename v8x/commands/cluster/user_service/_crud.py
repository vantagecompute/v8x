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
"""Shared CRUD operations for user services (remote-desktop, cloud-shell, pvc-viewer)."""

import json
from typing import Any

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import (
    get_auth_headers,
    get_cluster_with_creds,
    get_http_client,
    get_username,
    get_vdeployer_web_url,
)


def make_create_command(service_type: str):
    """Create a command bound to a specific service type."""

    @handle_abort
    @attach_settings
    @attach_persona
    @attach_vantage_rest_client
    async def create(
        ctx: typer.Context,
        cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
        node_group: Annotated[
            str | None, typer.Option("--node-group", "-n", help="Compute pool for scheduling")
        ] = None,
        resolution: Annotated[
            str, typer.Option("--resolution", "-r", help="Screen resolution (remote-desktop only)")
        ] = "1920x1080",
        image_version: Annotated[
            str | None, typer.Option("--image-version", help="Container image version")
        ] = None,
        slurm_cluster: Annotated[
            str | None, typer.Option("--slurm-cluster", help="Slurm cluster name")
        ] = None,
    ):
        console = ctx.obj.console
        try:
            cluster = await get_cluster_with_creds(ctx, cluster_name)
            url = (
                f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/service"
            )
            username = get_username(ctx)

            body: dict[str, Any] = {
                "service_type": service_type,
                "username": username,
            }
            if node_group:
                body["node_group"] = node_group
            if resolution and service_type == "remote-desktop":
                body["resolution"] = resolution
            if slurm_cluster:
                body["slurm_cluster"] = slurm_cluster
            if image_version:
                version_field = {
                    "remote-desktop": "remote_desktop_image_version",
                    "cloud-shell": "ttyd_image_version",
                    "pvc-viewer": "filebrowser_image_version",
                }.get(service_type)
                if version_field:
                    body[version_field] = image_version

            console.print(
                f"[dim]Creating {service_type} for '{username}' on '{cluster_name}'...[/dim]"
            )

            async with get_http_client() as client:
                response = await client.post(url, json=body, headers=get_auth_headers(ctx))

            if response.status_code == 200:
                data = response.json()
                if ctx.obj.json_output:
                    print(json.dumps(data, default=str))
                else:
                    console.print(f"[green]✓[/green] {service_type} created")
                    console.print(f"  ID:     {data.get('id', 'N/A')}")
                    console.print(f"  URL:    {data.get('url', 'N/A')}")
                    console.print(f"  Status: {data.get('status', 'N/A')}")
            else:
                _print_error(console, response)

        except Abort:
            raise
        except Exception as e:
            ctx.obj.formatter.render_error(
                error_message=f"Failed to create {service_type}.",
                details={"error": str(e)},
            )

    create.__doc__ = f"""Create a {service_type} on a Vantage cluster.

    Examples:
        v8x cluster user-service {service_type} create -c my-cluster
        v8x cluster user-service {service_type} create -c my-cluster -n {service_type.split("-")[0]}-sm
    """
    return create


def make_list_command(service_type: str):
    @handle_abort
    @attach_settings
    @attach_persona
    @attach_vantage_rest_client
    async def list_svc(
        ctx: typer.Context,
        cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    ):
        console = ctx.obj.console
        try:
            cluster = await get_cluster_with_creds(ctx, cluster_name)
            url = (
                f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/service"
            )

            async with get_http_client() as client:
                response = await client.get(
                    url,
                    params={"service_type": service_type},
                    headers=get_auth_headers(ctx),
                )

            if response.status_code != 200:
                raise Abort(f"Failed to list: {response.text}", subject="API Error")

            items = response.json()

            if ctx.obj.json_output:
                print(json.dumps(items, default=str))
                return

            if not items:
                console.print(f"No {service_type} instances found on '{cluster_name}'")
                return

            from rich.table import Table

            table = Table(title=f"{service_type} on '{cluster_name}'")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="bold")
            table.add_column("User")
            table.add_column("Status")
            table.add_column("URL")

            for s in items:
                table.add_row(
                    s.get("id", ""),
                    s.get("name", ""),
                    s.get("username", ""),
                    s.get("status", ""),
                    s.get("url", "") or "[dim]-[/dim]",
                )
            console.print(table)

        except Abort:
            raise
        except Exception as e:
            ctx.obj.formatter.render_error(
                error_message=f"Failed to list {service_type}.",
                details={"error": str(e)},
            )

    list_svc.__doc__ = f"""List {service_type} instances on a cluster.

    Examples:
        v8x cluster user-service {service_type} list -c my-cluster
    """
    return list_svc


def make_get_command(service_type: str):
    @handle_abort
    @attach_settings
    @attach_persona
    @attach_vantage_rest_client
    async def get_svc(
        ctx: typer.Context,
        service_id: Annotated[str, typer.Argument(help="Service ID")],
        cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    ):
        console = ctx.obj.console
        try:
            cluster = await get_cluster_with_creds(ctx, cluster_name)
            url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/service/{service_type}/{service_id}"

            async with get_http_client() as client:
                response = await client.get(url, headers=get_auth_headers(ctx))

            if response.status_code == 404:
                console.print(f"[yellow]{service_type} '{service_id}' not found[/yellow]")
                return

            if response.status_code != 200:
                raise Abort(f"Failed to get: {response.text}", subject="API Error")

            data = response.json()

            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
                return

            from rich.panel import Panel
            from rich.table import Table

            table = Table(show_header=False, box=None, pad_edge=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")

            for field in [
                "id",
                "name",
                "service_type",
                "username",
                "status",
                "url",
                "namespace",
                "resolution",
                "slurm_cluster",
                "created_at",
            ]:
                val = data.get(field)
                if val is not None:
                    table.add_row(field.replace("_", " ").title(), str(val))

            console.print(Panel(table, title=f"{service_type}: {service_id}"))

        except Abort:
            raise
        except Exception as e:
            ctx.obj.formatter.render_error(
                error_message=f"Failed to get {service_type} '{service_id}'.",
                details={"error": str(e)},
            )

    get_svc.__doc__ = f"""Get details of a {service_type} instance.

    Examples:
        v8x cluster user-service {service_type} get <id> -c my-cluster
    """
    return get_svc


def make_delete_command(service_type: str):
    @handle_abort
    @attach_settings
    @attach_persona
    @attach_vantage_rest_client
    async def delete_svc(
        ctx: typer.Context,
        service_id: Annotated[str, typer.Argument(help="Service ID")],
        cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
        force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
    ):
        console = ctx.obj.console

        if not force:
            if not typer.confirm(f"Delete {service_type} '{service_id}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            cluster = await get_cluster_with_creds(ctx, cluster_name)
            url = (
                f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/service"
            )

            async with get_http_client() as client:
                response = await client.request(
                    "DELETE",
                    url,
                    json={"service_type": service_type, "id": service_id},
                    headers=get_auth_headers(ctx),
                )

            if response.status_code in (200, 204):
                console.print(f"[green]✓[/green] {service_type} '{service_id}' deleted")
            elif response.status_code == 404:
                console.print(f"[yellow]{service_type} '{service_id}' not found[/yellow]")
            else:
                _print_error(console, response)

        except Abort:
            raise
        except Exception as e:
            ctx.obj.formatter.render_error(
                error_message=f"Failed to delete {service_type} '{service_id}'.",
                details={"error": str(e)},
            )

    delete_svc.__doc__ = f"""Delete a {service_type} from a cluster.

    Examples:
        v8x cluster user-service {service_type} delete <id> -c my-cluster
        v8x cluster user-service {service_type} delete <id> -c my-cluster --force
    """
    return delete_svc


def _print_error(console, response):
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    console.print(f"[red]Error:[/red] {response.status_code}: {detail}")
