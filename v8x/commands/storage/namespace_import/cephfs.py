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
"""CephFS storage import commands.

Import CephFS storage into a cluster namespace as PV/PVC. Supports both
internal imports (from another PVC in the cluster) and external imports
(from CephFS storage outside the cluster using monitor addresses and keys).
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

cephfs_app = AsyncTyper(name="cephfs", help="CephFS storage import operations.")


@cephfs_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_cephfs_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name for the imported PVC")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    source_pvc: Annotated[str, typer.Option("--source-pvc", help="Source CephFS PVC name")],
    source_namespace: Annotated[
        str, typer.Option("--source-namespace", help="Source CephFS PVC namespace")
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
    """Import CephFS storage from another PVC in the cluster."""
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
            "source_pvc": source_pvc,
            "source_namespace": source_namespace,
            "labels": get_username_label(ctx.obj.persona),
        }

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Import CephFS '{name}'",
            step_names=[] if json_output else ["Importing CephFS storage", "Done"],
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
                renderer.complete_step("Importing CephFS storage")
                formatter.render_create(data=result, resource_name="CephFS Import")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to import CephFS storage: {detail}", subject="Import Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="create-external")
@handle_abort
@attach_settings
@attach_persona
async def create_external_cephfs_import(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique name for this external import")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    ceph_monitors: Annotated[
        str, typer.Option("--ceph-monitors", help="Comma-separated Ceph mon addresses")
    ],
    ceph_client_name: Annotated[str, typer.Option("--ceph-client", help="Ceph client name")],
    ceph_client_key: Annotated[
        str, typer.Option("--ceph-client-key", help="Ceph client key (base64)")
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
    no_pvc: Annotated[
        bool, typer.Option("--no-pvc", help="Do not create a PVC (PV only)")
    ] = False,
    ceph_fs_name: Annotated[
        Optional[str], typer.Option("--ceph-fs-name", help="CephFS filesystem name")
    ] = None,
    ceph_root_path: Annotated[
        Optional[str], typer.Option("--ceph-root-path", help="CephFS root path to mount")
    ] = None,
) -> None:
    r"""Import CephFS storage from outside the cluster.

    Example:
      v8x storage import cephfs create-external my-ceph -c mycluster \
          --ceph-monitors 10.0.0.1:6789,10.0.0.2:6789 \
          --ceph-client admin --ceph-client-key AQD...== \
          --ceph-fs-name cephfs --ceph-root-path /
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
            "ceph_monitors": ceph_monitors,
            "ceph_client_name": ceph_client_name,
            "ceph_client_key": ceph_client_key,
            "labels": get_username_label(ctx.obj.persona),
        }
        if ceph_fs_name:
            payload["ceph_fs_name"] = ceph_fs_name
        if ceph_root_path:
            payload["ceph_root_path"] = ceph_root_path

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"External CephFS import '{name}'",
            step_names=[] if json_output else ["Importing external CephFS", "Done"],
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
                renderer.complete_step("Importing external CephFS")
                formatter.render_create(data=result, resource_name="External CephFS Import")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to import external CephFS: {detail}", subject="Import Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
