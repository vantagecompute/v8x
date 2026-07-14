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
    workload: Annotated[
        str,
        typer.Argument(
            help=f"Workload to create. Valid workloads: {', '.join(sorted(USER_SERVICES))}"
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
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help="Optional custom service name (auto-generated when omitted).",
        ),
    ] = None,
    preset: Annotated[
        str | None,
        typer.Option(
            "--sizing-preset",
            "-p",
            help="Sizing preset name supplying cpu/memory and the compute pool "
            "(see 'v8x cluster sizing-preset list --kind user-service').",
        ),
    ] = None,
    configuration_preset: Annotated[
        str | None,
        typer.Option(
            "--configuration-preset",
            "-C",
            help="Configuration preset name supplying image version, Slurm attachment, "
            "and extra labels (see 'v8x cluster configuration-preset list --kind user-service').",
        ),
    ] = None,
    image: Annotated[
        str | None,
        typer.Option(
            "--image",
            help="Image override: a bare tag replaces the version on the workload's "
            "default registry image; a value containing '/' or ':' is used as a full reference.",
        ),
    ] = None,
    resolution: Annotated[
        str | None,
        typer.Option(
            "--resolution",
            "-r",
            help="Desktop resolution for remote-desktop (e.g., 1920x1080).",
        ),
    ] = None,
):
    r"""Create a user service on a Vantage cluster.

    Creates a user-specific service like PVC viewer, cloud shell, or remote desktop.
    The username is automatically determined from your authenticated identity, and
    sizing/scheduling comes from the referenced preset.

    Examples:
        # Create a PVC viewer with workload defaults
        v8x cluster service create pvc-viewer --cluster my-cluster

        # Create a cloud shell from the split presets
        v8x cluster service create cloud-shell -c my-cluster \\
            --sizing-preset shell-sm --configuration-preset shell-sm

        # Create a remote desktop with a resolution override
        v8x cluster service create remote-desktop -c my-cluster \\
            -p desktop-md -C desktop-md -r 2560x1440

        # Create a cloud shell with a specific image tag
        v8x cluster service create cloud-shell -c my-cluster --image resolute-0.2
    """
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    # Username comes from the JWT server-side; resolve it locally only for output.
    persona = ctx.obj.persona
    if not persona or not persona.identity_data or not persona.identity_data.username:
        raise Abort(
            "Could not determine username from authentication token. Please log in again.",
            subject="Authentication Error",
            log_message="No persona or username in token",
        )
    username = persona.identity_data.username

    workload_lower = workload.lower()

    try:
        console.print(f"[dim]Creating {workload_lower} for user '{username}'...[/dim]")

        response = await user_service_sdk.create(
            ctx,
            cluster_name=cluster_name,
            workload=workload_lower,
            name=name,
            sizing_preset=preset,
            configuration_preset=configuration_preset,
            image=image,
            resolution=resolution,
        )

        if response.status_code == 200:
            result = response.json()
            formatter.success(f"{workload_lower} created for user '{username}'")
            console.print(f"  Service ID: {result.get('id', 'N/A')}")
            console.print(f"  URL: {result.get('url', 'N/A')}")
            console.print(f"  Status: {result.get('status', 'N/A')}")
            if result.get("sizing_preset"):
                console.print(f"  Sizing Preset: {result.get('sizing_preset')}")
            if result.get("configuration_preset"):
                console.print(f"  Configuration Preset: {result.get('configuration_preset')}")
            options = result.get("options") or {}
            if options.get("image"):
                console.print(f"  Image: {options.get('image')}")
            if options.get("resolution"):
                console.print(f"  Resolution: {options.get('resolution')}")
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
            error_message=f"Failed to create {workload_lower} for user '{username}'.",
            details={"error": str(e)},
        )
