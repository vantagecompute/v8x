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
"""Storage system lifecycle commands.

Manage storage systems (CephFS, CephNFS, etc.) through the vdeployer-web API.
Storage systems are tracked as ConfigMaps in the cluster and represent
deployed storage infrastructure components.
"""

from typing import Annotated, Optional

import typer
from vantage_sdk.exceptions import Abort

from v8x import AsyncTyper
from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.render import RenderStepOutput

from ._helpers import get_http_client, get_vdeployer_web_url

system_app = AsyncTyper(
    name="system",
    help="Manage storage system deployments (CephFS, CephNFS, etc.).",
    invoke_without_command=True,
    no_args_is_help=True,
)


@system_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_system(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique name for the storage system")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    system_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage system type (e.g. cephfs, cephnfs)"),
    ],
    storage_class_name: Annotated[
        str,
        typer.Option("--storage-class", help="Kubernetes StorageClass name for this system"),
    ],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace for system resources")
    ] = "vantage-rook-ceph",
    description: Annotated[
        Optional[str], typer.Option("--description", help="Human-readable description")
    ] = None,
    config_json: Annotated[
        Optional[str],
        typer.Option("--config", help="JSON string with extra configuration"),
    ] = None,
) -> None:
    """Create a new storage system registration."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        payload: dict = {
            "name": name,
            "namespace": namespace,
            "source": "system",
            "system_type": system_type,
            "storage_class": storage_class_name,
        }
        if config_json:
            import json

            payload["config"] = json.loads(config_json)

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Create storage system '{name}'",
            step_names=[] if json_output else ["Creating storage system", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/cephfs", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Creating storage system")
                formatter.render_create(data=result, resource_name="Storage System")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to create storage system: {detail}", subject="Create Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@system_app.command(name="get")
@handle_abort
@attach_settings
@attach_persona
async def get_system(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the storage system")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace for system resources")
    ] = "vantage-rook-ceph",
) -> None:
    """Get details of a storage system."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Get storage system '{name}'",
            step_names=[] if json_output else ["Fetching storage system", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(f"{vdeployer_url}/storage/cephfs/{namespace}/{name}")

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching storage system")
                formatter.render_get(data=result, resource_name="Storage System")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"Storage system '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get storage system: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@system_app.command(name="list")
@handle_abort
@attach_settings
@attach_persona
async def list_systems(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
) -> None:
    """List all registered storage systems."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name="List storage systems",
            step_names=[] if json_output else ["Fetching storage systems", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/cephfs", params={"source": "system"}
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching storage systems")
                formatter.render_list(
                    data=result.get("volumes", []),
                    resource_name="Storage System",
                )
                renderer.complete_step("Done")
        else:
            raise Abort(f"Failed to list storage systems: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@system_app.command(name="delete")
@handle_abort
@attach_settings
@attach_persona
async def delete_system(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the storage system to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace for system resources")
    ] = "vantage-rook-ceph",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a storage system registration."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    if not force and not typer.confirm(f"Delete storage system '{name}'?"):
        ctx.obj.console.print("[yellow]Cancelled.[/yellow]")
        return

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Delete storage system '{name}'",
            step_names=[] if json_output else ["Deleting storage system", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.delete(f"{vdeployer_url}/storage/cephfs/{namespace}/{name}")

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Deleting storage system")
                formatter.success(f"Storage system '{name}' deleted")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"Storage system '{name}' not found.", subject="Not Found")
        else:
            raise Abort(
                f"Failed to delete storage system: {response.text}", subject="Delete Failed"
            )

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@system_app.command(name="update")
@handle_abort
@attach_settings
@attach_persona
async def update_system(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the storage system to update")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace for system resources")
    ] = "vantage-rook-ceph",
    storage_class_name: Annotated[
        Optional[str], typer.Option("--storage-class", help="New StorageClass name")
    ] = None,
    config_json: Annotated[
        Optional[str],
        typer.Option("--config", help="JSON string with updated configuration"),
    ] = None,
) -> None:
    """Update a storage system's configuration."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        payload: dict = {}
        if storage_class_name:
            payload["storage_class_name"] = storage_class_name
        if config_json:
            import json

            payload["config"] = json.loads(config_json)

        if not payload:
            raise Abort(
                "No fields to update. Use --storage-class or --config.",
                subject="No Updates",
            )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Update storage system '{name}'",
            step_names=[] if json_output else ["Updating storage system", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.put(
                f"{vdeployer_url}/storage/cephfs/{namespace}/{name}", json=payload
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Updating storage system")
                formatter.render_get(data=result, resource_name="Storage System")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"Storage system '{name}' not found.", subject="Not Found")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to update storage system: {detail}", subject="Update Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
