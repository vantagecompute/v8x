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
"""Cross-namespace (internal) storage import commands.

Import storage from one cluster namespace into another by creating a
matching PV/PVC pair in the target namespace.
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
    get_username_label,
    get_vdeployer_web_url,
    resolve_namespace,
)

internal_app = AsyncTyper(
    name="internal",
    help="Import storage across namespaces within the cluster.",
)


@internal_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_internal_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name for the imported PVC in the target namespace")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    source_pvc: Annotated[str, typer.Option("--source-pvc", help="Source PVC name")],
    source_namespace: Annotated[
        str, typer.Option("--source-namespace", help="Source PVC namespace")
    ],
    namespace: Annotated[
        Optional[str],
        typer.Option(
            "--namespace", "-n", help="Target namespace (default: derived from username)"
        ),
    ] = None,
    capacity: Annotated[str, typer.Option("--capacity", help="Storage capacity")] = "100Gi",
    access_mode: Annotated[
        str,
        typer.Option(
            "--access-mode", help="Access mode (ReadWriteMany, ReadOnlyMany, ReadWriteOnce)"
        ),
    ] = "ReadWriteMany",
    read_only: Annotated[bool, typer.Option("--read-only", help="Mount as read-only")] = False,
) -> None:
    """Import existing PVC from another namespace into the target namespace."""
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

        payload = {
            "name": name,
            "namespace": namespace,
            "source": "internal",
            "source_pvc": source_pvc,
            "source_namespace": source_namespace,
            "capacity": capacity,
            "access_modes": [access_mode],
            "read_only": read_only,
            "labels": get_username_label(ctx.obj.persona),
        }

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Import storage '{name}' (cross-namespace)",
            step_names=[] if json_output else ["Importing storage", "Done"],
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
                renderer.complete_step("Importing storage")
                formatter.render_create(data=result, resource_name="Cross-Namespace Import")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(
                f"Failed to create cross-namespace import: {detail}", subject="Import Failed"
            )

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@internal_app.command(name="get")
@handle_abort
@attach_settings
@attach_persona
async def get_internal_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the imported PVC")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """Get details of a cross-namespace storage import."""
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
            response = await client.get(f"{vdeployer_url}/storage/cephfs/{namespace}/{name}")

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching import")
                formatter.render_get(data=result, resource_name="Cross-Namespace Import")
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


@internal_app.command(name="list")
@handle_abort
@attach_settings
@attach_persona
async def list_internal_imports(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
) -> None:
    """List all cross-namespace storage imports in a namespace."""
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
            operation_name="List cross-namespace imports",
            step_names=[] if json_output else ["Fetching imports", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/cephfs",
                params={"namespace": namespace, "source": "internal"},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching imports")
                formatter.render_list(
                    data=result.get("volumes", []),
                    resource_name="Cross-Namespace Import",
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


@internal_app.command(name="delete")
@handle_abort
@attach_settings
@attach_persona
async def delete_internal_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the imported PVC to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Namespace (default: derived from username)"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a cross-namespace storage import and its backing PV."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    namespace = resolve_namespace(ctx.obj.persona, namespace)

    if not force and not typer.confirm(
        f"Delete cross-namespace import '{name}' in namespace '{namespace}'?"
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
            response = await client.delete(f"{vdeployer_url}/storage/cephfs/{namespace}/{name}")

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
