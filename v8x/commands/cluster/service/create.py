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
"""Create user service command for v8x."""

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.user_service import USER_SERVICES, user_service_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_user_service(
    ctx: typer.Context,
    service_type: Annotated[
        str,
        typer.Argument(
            help=f"Service type to create. Valid types: {', '.join(sorted(USER_SERVICES))}"
        ),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the cluster",
        ),
    ],
    resolution: Annotated[
        str,
        typer.Option(
            "--resolution",
            "-r",
            help="Resolution for remote-desktop (e.g., 1920x1080)",
        ),
    ] = "1920x1080",
    source_namespace: Annotated[
        str,
        typer.Option(
            "--source-namespace",
            help="Namespace where cephfs-user-homes PVC exists",
        ),
    ] = "vantage-rook-ceph",
    source_pvc_name: Annotated[
        str,
        typer.Option(
            "--source-pvc-name",
            help="Name of source PVC",
        ),
    ] = "cephfs-user-homes",
    node_group: Annotated[
        str | None,
        typer.Option(
            "--node-group",
            "-n",
            help="Node group name for scheduling (e.g., 'desktop-lg', 'shell-sm'). "
            "Pods are scheduled to nodes with vc.pool=<name>.",
        ),
    ] = None,
    instance_type: Annotated[
        str | None,
        typer.Option(
            "--instance-type",
            "-i",
            help="Instance type for node selection (e.g., small, medium, large, gpu). "
            "Deprecated: use --node-group instead.",
        ),
    ] = None,
    image_version: Annotated[
        str | None,
        typer.Option(
            "--image-version",
            help="Image version to use for the service container.",
        ),
    ] = None,
):
    """Create a user service on a Vantage cluster.

    Creates a user-specific service like PVC viewer, cloud shell, or remote desktop.
    The username is automatically determined from your authenticated identity.

    Examples:
        # Create a PVC viewer
        v8x cluster service create pvc-viewer --cluster my-cluster

        # Create a cloud shell
        v8x cluster service create cloud-shell -c my-cluster

        # Create a remote desktop with specific resolution
        v8x cluster service create remote-desktop -c my-cluster -r 2560x1440

        # Create a remote desktop on a GPU node
        v8x cluster service create remote-desktop -c my-cluster -i gpu

        # Create a remote desktop with a specific image version
        v8x cluster service create remote-desktop -c my-cluster --image-version 1.2.3

        # Create a cloud shell with a specific image version
        v8x cluster service create cloud-shell -c my-cluster --image-version 0.9.0
    """
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    # Get username from authenticated persona
    persona = ctx.obj.persona
    if not persona or not persona.identity_data or not persona.identity_data.username:
        raise Abort(
            "Could not determine username from authentication token. Please log in again.",
            subject="Authentication Error",
            log_message="No persona or username in token",
        )
    username = persona.identity_data.username

    service_type_lower = service_type.lower()

    try:
        console.print(f"[dim]Creating {service_type_lower} for user '{username}'...[/dim]")

        response = await user_service_sdk.create(
            ctx,
            cluster_name=cluster_name,
            service_type=service_type_lower,
            username=username,
            resolution=resolution,
            source_namespace=source_namespace,
            source_pvc_name=source_pvc_name,
            node_group=node_group,
            instance_type=instance_type,
            image_version=image_version,
        )

        if response.status_code == 200:
            result = response.json()
            formatter.success(f"{service_type_lower} created for user '{username}'")
            console.print(f"  Service ID: {result.get('id', 'N/A')}")
            console.print(f"  URL: {result.get('url', 'N/A')}")
            console.print(f"  Status: {result.get('status', 'N/A')}")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to create service: {error_detail}",
                subject="Service Creation Failed",
                log_message=f"Service creation failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        formatter.render_error(
            error_message=f"Failed to create {service_type_lower} for user '{username}'.",
            details={"error": str(e)},
        )
