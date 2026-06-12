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
"""Namespace import command group.

Organises all storage import operations under ``v8x storage import``:

* ``internal`` – cross‑namespace PVC imports
* ``cephfs``   – CephFS imports (internal + external)
* ``nfs``      – NFS imports (internal + external)

Shared CRUD commands (get / list / delete) that operate across import types
live here at the top‑level import group, while type‑specific *create*
commands live in their respective sub‑modules.
"""

from typing import Annotated, Optional

import typer
from vantage_sdk.exceptions import Abort

from v8x import AsyncTyper
from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.render import RenderStepOutput

from .._helpers import (
    get_http_client,
    get_username_from_persona,
    get_vdeployer_web_url,
    resolve_namespace,
)
from .cephfs import cephfs_app
from .internal import internal_app
from .nfs import nfs_app

# ---------------------------------------------------------------------------
# Import subcommand group
# ---------------------------------------------------------------------------

import_app = AsyncTyper(
    name="import",
    help="Import storage into cluster namespaces.",
    invoke_without_command=True,
    no_args_is_help=True,
)

# Register type‑specific subcommand groups
import_app.add_typer(internal_app, name="internal")
import_app.add_typer(cephfs_app, name="cephfs")
import_app.add_typer(nfs_app, name="nfs")


# ---------------------------------------------------------------------------
# Shared namespace‑scoped commands (standard NFS/CephFS imports)
# ---------------------------------------------------------------------------


@import_app.command(name="get")
@handle_abort
@attach_settings
@attach_persona
async def get_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the imported PVC")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get details of a specific storage import."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Get import '{name}'",
            step_names=[] if json_output else ["Fetching import", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/{storage_type}/{namespace}/{name}"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching import")
                formatter.render_get(data=result, resource_name="Imported Storage")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(
                f"Import '{name}' not found in namespace '{namespace}'.", subject="Not Found"
            )
        else:
            raise Abort(f"Failed to get import: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="list")
@handle_abort
@attach_settings
@attach_persona
async def list_imports(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """List all storage imports in a namespace."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name="List imports",
            step_names=[] if json_output else ["Fetching imports", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            username = get_username_from_persona(ctx.obj.persona)
            params: dict[str, str] = {"namespace": namespace}
            if username:
                params["username"] = username
            response = await client.get(f"{vdeployer_url}/storage/{storage_type}", params=params)

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            # Response key varies by type
            items_key = "nfs_mounts" if storage_type == "nfs" else "volumes"
            with renderer:
                renderer.complete_step("Fetching imports")
                formatter.render_list(
                    data=result.get(items_key, []),
                    resource_name="Imported Storage",
                )
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"Namespace '{namespace}' not found.", subject="Namespace Not Found")
        else:
            raise Abort(f"Failed to list imports: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="delete")
@handle_abort
@attach_settings
@attach_persona
async def delete_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the imported PVC to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an imported storage PVC and its backing PV."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    if not force and not typer.confirm(
        f"Delete imported storage '{name}' in namespace '{namespace}'?"
    ):
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
            operation_name=f"Delete import '{name}'",
            step_names=[] if json_output else ["Deleting import", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.delete(
                f"{vdeployer_url}/storage/{storage_type}/{namespace}/{name}"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Deleting import")
                formatter.success(f"Import '{name}' deleted from namespace '{namespace}'")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(
                f"Import '{name}' not found in namespace '{namespace}'.", subject="Not Found"
            )
        else:
            raise Abort(f"Failed to delete import: {response.text}", subject="Delete Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


# ---------------------------------------------------------------------------
# Shared external import commands
# ---------------------------------------------------------------------------


@import_app.command(name="get-external")
@handle_abort
@attach_settings
@attach_persona
async def get_external_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get details of a specific external import."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Get external import '{name}'",
            step_names=[] if json_output else ["Fetching external import", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/{storage_type}/{namespace}/{name}"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching external import")
                formatter.render_get(data=result, resource_name="External Import")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"External import '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get external import: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="list-external")
@handle_abort
@attach_settings
@attach_persona
async def list_external_imports(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Filter by namespace"),
    ] = None,
) -> None:
    """List all external imports."""
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
            operation_name="List external imports",
            step_names=[] if json_output else ["Fetching external imports", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        params: dict[str, str] = {"source": "external"}
        if namespace:
            params["namespace"] = namespace

        async with get_http_client(ctx) as client:
            response = await client.get(f"{vdeployer_url}/storage/{storage_type}", params=params)

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            items_key = "nfs_mounts" if storage_type == "nfs" else "volumes"
            with renderer:
                renderer.complete_step("Fetching external imports")
                formatter.render_list(
                    data=result.get(items_key, []),
                    resource_name="External Import",
                )
                renderer.complete_step("Done")
        else:
            raise Abort(f"Failed to list external imports: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="delete-external")
@handle_abort
@attach_settings
@attach_persona
async def delete_external_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external import to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace override"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an external import (PV, PVC, and credentials)."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    if not force and not typer.confirm(f"Delete external import '{name}'?"):
        ctx.obj.console.print("[yellow]Cancelled.[/yellow]")
        return

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Delete external import '{name}'",
            step_names=[] if json_output else ["Deleting external import", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.delete(
                f"{vdeployer_url}/storage/{storage_type}/{namespace}/{name}"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Deleting external import")
                formatter.success(f"External import '{name}' deleted")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"External import '{name}' not found.", subject="Not Found")
        else:
            raise Abort(
                f"Failed to delete external import: {response.text}", subject="Delete Failed"
            )

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="external-status")
@handle_abort
@attach_settings
@attach_persona
async def external_import_status(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    storage_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Storage type: 'nfs' or 'cephfs'"),
    ] = "nfs",
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get PV/PVC binding status of an external import."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Status for '{name}'",
            step_names=[] if json_output else ["Fetching status", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/{storage_type}/{namespace}/{name}/status"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching status")
                formatter.render_get(data=result, resource_name="External Import Status")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"External import '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get status: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="external-mount-info")
@handle_abort
@attach_settings
@attach_persona
async def external_import_mount_info(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get mount information for an external import (NFS only)."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Mount info for '{name}'",
            step_names=[] if json_output else ["Fetching mount info", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/nfs/{namespace}/{name}/mount-info"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching mount info")
                formatter.render_get(data=result, resource_name="Mount Info")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"External import '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get mount info: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@import_app.command(name="external-config")
@handle_abort
@attach_settings
@attach_persona
async def external_import_config(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get the full configuration of an external import as reusable JSON (CephFS only)."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    try:
        vdeployer_url = get_vdeployer_web_url(
            cluster_name=cluster_name,
            org_id=ctx.obj.persona.identity_data.org_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Config for '{name}'",
            step_names=[] if json_output else ["Fetching config", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/cephfs/{namespace}/{name}/config"
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching config")
                formatter.render_get(data=result, resource_name="External Import Config")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"External import '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get config: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
