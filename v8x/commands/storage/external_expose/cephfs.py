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
"""CephFS external expose commands.

Expose in-cluster CephFS storage to clients outside the Kubernetes cluster.
Creates Ceph client credentials, exposes monitors, and returns mount commands.
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

cephfs_app = AsyncTyper(name="cephfs", help="CephFS external expose operations.")


@cephfs_app.command(name="create")
@handle_abort
@attach_settings
@attach_persona
async def create_cephfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Unique name for this external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    ceph_client_name: Annotated[str, typer.Option(help="Ceph client name")] = "external-cephfs",
    ceph_mds_path: Annotated[str, typer.Option(help="MDS permission path")] = "/volumes/csi",
    ceph_osd_pool: Annotated[str, typer.Option(help="OSD pool name")] = "vantage-cephfs-data",
    expose_monitors: Annotated[bool, typer.Option(help="Expose Ceph monitors")] = True,
    monitor_service_type: Annotated[
        str, typer.Option(help="NodePort or LoadBalancer")
    ] = "NodePort",
    msgr2_node_port: Annotated[int, typer.Option(help="NodePort for msgr2")] = 30300,
    msgr1_node_port: Annotated[int, typer.Option(help="NodePort for msgr1")] = 30789,
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Expose CephFS storage to clients outside the cluster."""
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
            operation_name=f"Expose CephFS '{name}' externally",
            step_names=[] if json_output else ["Creating external expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        payload = {
            "storage_type": "cephfs",
            "name": name,
            "ceph_client_name": ceph_client_name,
            "ceph_mds_path": ceph_mds_path,
            "ceph_osd_pool": ceph_osd_pool,
            "expose_monitors": expose_monitors,
            "monitor_service_type": monitor_service_type,
            "msgr2_node_port": msgr2_node_port,
            "msgr1_node_port": msgr1_node_port,
            "rook_namespace": rook_namespace,
        }

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/expose", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Creating external expose")
                formatter.render_create(data=result, resource_name="External CephFS Expose")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(f"Failed to create CephFS expose: {detail}", subject="Expose Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="get")
@handle_abort
@attach_settings
@attach_persona
async def get_cephfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Get details of a CephFS external expose."""
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
            operation_name=f"Get CephFS expose '{name}'",
            step_names=[] if json_output else ["Fetching expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose/{name}",
                params={"storage_type": "cephfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching expose")
                formatter.render_get(data=result, resource_name="External CephFS Expose")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"CephFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get expose: {response.text}", subject="Get Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="list")
@handle_abort
@attach_settings
@attach_persona
async def list_cephfs_exposes(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """List all external exposes."""
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
            operation_name="List external exposes",
            step_names=[] if json_output else ["Fetching exposes", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose",
                params={"rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching exposes")
                formatter.render_list(
                    data=result.get("exposes", []),
                    resource_name="External Expose",
                )
                renderer.complete_step("Done")
        else:
            raise Abort(f"Failed to list exposes: {response.text}", subject="List Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="delete")
@handle_abort
@attach_settings
@attach_persona
async def delete_cephfs_expose(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose to delete")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a CephFS external expose."""
    json_output = getattr(ctx.obj, "json_output", False)
    verbose = getattr(ctx.obj, "verbose", False)
    formatter = ctx.obj.formatter
    command_start_time = getattr(ctx.obj, "command_start_time", None) if ctx.obj else None

    if not force and not typer.confirm(f"Delete CephFS expose '{name}'?"):
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
            operation_name=f"Delete CephFS expose '{name}'",
            step_names=[] if json_output else ["Deleting expose", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.delete(
                f"{vdeployer_url}/storage/expose/{name}",
                params={"storage_type": "cephfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Deleting expose")
                formatter.success(f"CephFS expose '{name}' deleted")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"CephFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to delete expose: {response.text}", subject="Delete Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="mount-commands")
@handle_abort
@attach_settings
@attach_persona
async def cephfs_mount_commands(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Get mount commands for a CephFS external expose."""
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
            operation_name=f"Mount commands for '{name}'",
            step_names=[] if json_output else ["Fetching mount commands", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose/{name}/mount-commands",
                params={"storage_type": "cephfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching mount commands")
                formatter.render_get(data=result, resource_name="Mount Commands")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"CephFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get mount commands: {response.text}", subject="Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="credentials")
@handle_abort
@attach_settings
@attach_persona
async def cephfs_credentials(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Get CephFS credentials for an external expose."""
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
            operation_name=f"Credentials for '{name}'",
            step_names=[] if json_output else ["Fetching credentials", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose/{name}/credentials",
                params={"rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching credentials")
                formatter.render_get(data=result, resource_name="CephFS Credentials")
                renderer.complete_step("Done")
        elif response.status_code == 404:
            raise Abort(f"CephFS expose '{name}' not found.", subject="Not Found")
        else:
            raise Abort(f"Failed to get credentials: {response.text}", subject="Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e


@cephfs_app.command(name="status")
@handle_abort
@attach_settings
@attach_persona
async def cephfs_status(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the external expose")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    rook_namespace: Annotated[str, typer.Option(help="Rook-Ceph namespace")] = "vantage-rook-ceph",
) -> None:
    """Get status of a CephFS external expose."""
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
            operation_name=f"Status of expose '{name}'",
            step_names=[] if json_output else ["Fetching status", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.get(
                f"{vdeployer_url}/storage/expose/{name}/status",
                params={"storage_type": "cephfs", "rook_namespace": rook_namespace},
            )

        if response.status_code == 200:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Fetching status")
                formatter.render_get(data=result, resource_name="Expose Status")
                renderer.complete_step("Done")
        else:
            raise Abort(f"Failed to get status: {response.text}", subject="Failed")

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
