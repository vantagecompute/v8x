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
"""Get user service command for v8x."""

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
async def get_user_service(
    ctx: typer.Context,
    service_type: Annotated[
        str,
        typer.Argument(help=f"Service type. Valid types: {', '.join(sorted(USER_SERVICES))}"),
    ],
    service_id: Annotated[
        str,
        typer.Argument(help="UUID identifier of the service"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the cluster",
        ),
    ],
):
    """Get details of a specific user service.

    Examples:
        # Get details of a specific PVC viewer
        v8x cluster service get pvc-viewer abc12345-... --cluster my-cluster

        # Get details of a cloud shell
        v8x cluster service get cloud-shell def67890-... -c my-cluster
    """
    console = ctx.obj.console

    service_type_lower = service_type.lower()

    try:
        console.print(f"[dim]Fetching {service_type_lower} '{service_id[:8]}...'...[/dim]")

        response = await user_service_sdk.get(
            ctx,
            cluster_name=cluster_name,
            service_type=service_type_lower,
            service_id=service_id,
        )

        if response.status_code == 200:
            svc = response.json()
            console.print(f"\n[bold cyan]{svc.get('service_type', 'N/A')}[/bold cyan]")
            console.print(f"  ID: {svc.get('id', 'N/A')}")
            console.print(f"  Name: {svc.get('name', 'N/A')}")
            console.print(f"  Namespace: {svc.get('namespace', 'N/A')}")
            console.print(f"  Username: {svc.get('username', 'N/A')}")
            console.print(f"  Status: {svc.get('status', 'N/A')}")
            console.print(f"  Replicas: {svc.get('ready_replicas', 0)}/{svc.get('replicas', 1)}")
            if svc.get("url"):
                console.print(f"  URL: {svc.get('url')}")
            if svc.get("created_at"):
                console.print(f"  Created: {svc.get('created_at')}")
            if svc.get("pvc_name"):
                console.print(f"  PVC Name: {svc.get('pvc_name')}")
            if svc.get("resolution"):
                console.print(f"  Resolution: {svc.get('resolution')}")
        elif response.status_code == 404:
            raise Abort(
                f"Service not found: {service_id}",
                subject="Service Not Found",
                log_message=f"Service not found: {service_id}",
            )
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to get service: {error_detail}",
                subject="Service Get Failed",
                log_message=f"Service get failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get {service_type_lower} '{service_id[:8]}...'.",
            details={"error": str(e)},
        )
