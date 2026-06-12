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
"""NFS external expose commands.

Expose in-cluster NFS-backed PVCs to clients outside the Kubernetes cluster
by reading the backing NFS PV and returning mount information.
"""

from typing import Annotated

import typer
from vantage_sdk.exceptions import Abort

from v8x import AsyncTyper
from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.render import RenderStepOutput

from .._helpers import get_http_client, get_vdeployer_web_url

nfs_app = AsyncTyper(name="nfs", help="NFS external expose operations.")


@nfs_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_nfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique name for this external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    source_pvc: Annotated[str, typer.Option("--source-pvc", help="Source PVC name")],
    source_namespace: Annotated[
        str, typer.Option("--source-namespace", help="Source PVC namespace")
    ],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Expose NFS-backed PVC storage to clients outside the cluster."""
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

        payload = {
            "storage_type": "nfs",
            "name": name,
            "source_pvc": source_pvc,
            "source_namespace": source_namespace,
            "rook_namespace": rook_namespace,
        }

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Expose NFS '{name}' externally",
            step_names=[] if json_output else ["Creating external NFS expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/expose", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Creating external NFS expose")
                formatter.render_create(data=result, resource_name="External NFS Expose")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to expose NFS externally: {detail}", subject="Expose Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@nfs_app.command(name="get")
@handle_abort
@attach_settings
@attach_persona
async def get_nfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Get details of an NFS external expose."""
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
            operation_name=f"Get NFS expose '{name}'",
            step_names=[] if json_output else ["Fetching NFS expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose/{name}",
                params={"storage_type": "nfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching NFS expose")
                formatter.render_get(data=result, resource_name="External NFS Expose")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"NFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get NFS expose: {response.text}", subject="Error")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@nfs_app.command(name="delete")
@handle_abort
@attach_settings
@attach_persona
async def delete_nfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an NFS external expose."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    if not force and not typer.confirm(f"Delete NFS expose '{name}'?"):
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
            operation_name=f"Delete NFS expose '{name}'",
            step_names=[] if json_output else ["Deleting NFS expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.delete(
                f"{vdeployer_url}/storage/expose/{name}",
                params={"storage_type": "nfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Deleting NFS expose")
                formatter.success(f"NFS expose '{name}' deleted")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"NFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to delete NFS expose: {response.text}", subject="Delete Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
