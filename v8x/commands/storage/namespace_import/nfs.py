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
"""NFS storage import commands.

Import NFS storage into a cluster namespace as PV/PVC. Supports both
internal imports (from an NFS server visible to the cluster) and external
imports (from NFS storage outside the cluster).
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

nfs_app = AsyncTyper(name="nfs", help="NFS storage import operations.")


@nfs_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_nfs_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name for the imported PVC")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    nfs_server: Annotated[str, typer.Option("--nfs-server", help="NFS server hostname or IP")],
    nfs_share: Annotated[str, typer.Option("--nfs-share", help="NFS share/export path")],
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
    r"""Import NFS storage as a PVC in a cluster namespace.

    Example:
      v8x storage import nfs create my-nfs -c mycluster \
          --nfs-server 10.0.0.5 --nfs-share /exports/data
    """
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

        payload: dict = {
            "name": name,
            "namespace": namespace,
            "source": "internal",
            "capacity": capacity,
            "access_modes": [access_mode],
            "read_only": read_only,
            "nfs_server": nfs_server,
            "nfs_share": nfs_share,
            "labels": get_username_label(ctx.obj.persona),
        }

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Import NFS '{name}'",
            step_names=[] if json_output else ["Importing NFS storage", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/nfs", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Importing NFS storage")
                formatter.render_create(data=result, resource_name="NFS Import")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to import NFS storage: {detail}", subject="Import Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@nfs_app.command(name="create-external")
@handle_abort
@attach_settings
@attach_persona
async def create_external_nfs_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique name for this external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    nfs_server: Annotated[str, typer.Option("--nfs-server", help="NFS server hostname or IP")],
    nfs_share: Annotated[str, typer.Option("--nfs-share", help="NFS export path")],
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
    no_pvc: Annotated[
        bool, typer.Option("--no-pvc", help="Do not create a PVC (PV only)")
    ] = False,
) -> None:
    r"""Import external NFS storage into the cluster as PV + PVC.

    Example:
      v8x storage import nfs create-external my-nfs -c mycluster \
          --nfs-server 10.0.0.5 --nfs-share /exports/data
    """
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

        payload: dict = {
            "name": name,
            "namespace": namespace,
            "source": "external",
            "capacity": capacity,
            "access_modes": [access_mode],
            "read_only": read_only,
            "create_pvc": not no_pvc,
            "nfs_server": nfs_server,
            "nfs_share": nfs_share,
            "labels": get_username_label(ctx.obj.persona),
        }

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"External NFS import '{name}'",
            step_names=[] if json_output else ["Importing external NFS", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/nfs", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Importing external NFS")
                formatter.render_create(data=result, resource_name="External NFS Import")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to import external NFS: {detail}", subject="Import Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
