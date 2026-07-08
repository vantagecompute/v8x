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
"""Delete user service command for v8x."""

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
async def delete_user_service(
    ctx: typer.Context,
    workload: Annotated[
        str,
        typer.Argument(help=f"Workload. Valid workloads: {', '.join(sorted(USER_SERVICES))}"),
    ],
    service_id: Annotated[
        str,
        typer.Argument(help="UUID identifier of the service to delete"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the cluster",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """Delete a user service from a Vantage cluster.

    Removes the deployment, service, and associated resources.

    Examples:
        # Delete a PVC viewer
        v8x cluster service delete pvc-viewer abc12345-... --cluster my-cluster

        # Delete a cloud shell without confirmation
        v8x cluster service delete cloud-shell def67890-... -c my-cluster --force
    """
    console = ctx.obj.console
    formatter = ctx.obj.formatter

    workload_lower = workload.lower()

    # Confirm deletion unless --force is used
    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete {workload_lower} '{service_id[:8]}...'?"
        )
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        console.print(f"[dim]Deleting {workload_lower} '{service_id[:8]}...'...[/dim]")

        response = await user_service_sdk.delete(
            ctx,
            cluster_name=cluster_name,
            workload=workload_lower,
            service_id=service_id,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                formatter.success(f"{workload_lower} '{service_id[:8]}...' deleted")
            else:
                console.print(f"[yellow]{result.get('message', 'Delete returned false')}[/yellow]")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to delete service: {error_detail}",
                subject="Service Delete Failed",
                log_message=f"Service delete failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        formatter.render_error(
            error_message=f"Failed to delete {workload_lower} '{service_id[:8]}...'.",
            details={"error": str(e)},
        )
