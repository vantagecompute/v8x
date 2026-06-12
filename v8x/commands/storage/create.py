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
"""Create storage (PVC) command."""

from typing import Annotated, Optional

import typer
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.render import RenderStepOutput

from ._helpers import get_http_client, get_vdeployer_web_url, resolve_namespace


@handle_abort
@attach_settings
@attach_persona
async def create_storage(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the PVC to create")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    namespace: Annotated[
        Optional[str],
        typer.Option(
            "--namespace", "-n", help="Target namespace (default: derived from username)"
        ),
    ] = None,
    size: Annotated[str, typer.Option("--size", "-s", help="Storage size (e.g. 10Gi)")] = "10Gi",
    storage_class: Annotated[
        Optional[str],
        typer.Option("--storage-class", help="StorageClass name (cluster default if omitted)"),
    ] = None,
    access_mode: Annotated[
        str,
        typer.Option(
            "--access-mode", help="Access mode (ReadWriteOnce, ReadWriteMany, ReadOnlyMany)"
        ),
    ] = "ReadWriteOnce",
):
    """Create a PersistentVolumeClaim in a cluster namespace."""
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
            "size": size,
            "access_modes": [access_mode],
        }
        if storage_class:
            payload["storage_class"] = storage_class

        renderer = RenderStepOutput(
            console=ctx.obj.console,
            operation_name=f"Create PVC '{name}'",
            step_names=[] if json_output else ["Creating PVC", "Done"],
            verbose=verbose,
            command_start_time=command_start_time,
        )

        async with get_http_client(ctx) as client:
            response = await client.post(f"{vdeployer_url}/storage/pvc", json=payload)

        if response.status_code == 201:
            result = response.json()
            if json_output:
                return renderer.json_bypass(result)
            with renderer:
                renderer.complete_step("Creating PVC")
                formatter.render_create(data=result, resource_name="PVC")
                renderer.complete_step("Done")
        else:
            detail = (
                response.json().get("detail", response.text)
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            raise Abort(
                f"Failed to create PVC: {detail}",
                subject="Create PVC Failed",
            )

    except Abort:
        raise
    except Exception as e:
        raise Abort(f"Unexpected error: {e}", subject="Error") from e
