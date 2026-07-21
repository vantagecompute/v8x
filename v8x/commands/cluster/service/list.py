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
"""List user services command for v8x."""

import typer
from rich.table import Table
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
async def list_user_services(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the cluster",
        ),
    ],
    workload: Annotated[
        str | None,
        typer.Option(
            "--workload",
            "-w",
            "--type",
            "-t",
            help=f"Filter by workload: {', '.join(sorted(USER_SERVICES))}",
        ),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option(
            "--username",
            "-u",
            help="Filter by username (defaults to current user)",
        ),
    ] = None,
    all_users: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Show services for all users (admin only)",
        ),
    ] = False,
):
    """List user services on a Vantage cluster.

    Lists user-specific services like PVC viewers, cloud shells, and remote desktops.
    By default, shows only your own services.

    Examples:
        # List your services
        v8x cluster service list --cluster my-cluster

        # List only your cloud shells
        v8x cluster service list -c my-cluster --workload cloud-shell

        # List services for a specific user (admin)
        v8x cluster service list -c my-cluster --username alice

        # List all users' services (admin)
        v8x cluster service list -c my-cluster --all
    """
    console = ctx.obj.console

    # Default to current user's services unless --all or --username specified
    if not all_users and username is None:
        persona = ctx.obj.persona
        if persona and persona.identity_data and persona.identity_data.username:
            username = persona.identity_data.username

    if workload:
        workload = workload.lower()

    try:
        console.print("[dim]Fetching services...[/dim]")

        response = await user_service_sdk.list(
            ctx,
            cluster_name=cluster_name,
            workload=workload,
            username=username,
        )

        if response.status_code == 200:
            result = response.json()
            services = result.get("services", [])
            count = result.get("count", len(services))

            if count == 0:
                console.print("[yellow]No services found[/yellow]")
                return

            # Create a table
            table = Table(title=f"User Services ({count} total)")
            table.add_column("Workload", style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("Username", style="green")
            table.add_column("Size Preset", style="magenta")
            table.add_column("Config Preset", style="magenta")
            table.add_column("Status")
            table.add_column("Replicas")
            table.add_column("URL", style="dim")

            for svc in services:
                status_style = "green" if svc.get("status") == "Running" else "yellow"
                replicas = f"{svc.get('ready_replicas', 0)}/{svc.get('replicas', 1)}"
                url = svc.get("url", "N/A") or "N/A"
                # Truncate URL for display
                if len(url) > 40:
                    url = url[:37] + "..."

                table.add_row(
                    svc.get("workload", "N/A"),
                    svc.get("id", "N/A")[:8],  # Show first 8 chars of UUID
                    svc.get("username", "N/A"),
                    svc.get("size_preset") or "-",
                    svc.get("configuration_preset") or "-",
                    f"[{status_style}]{svc.get('status', 'N/A')}[/{status_style}]",
                    replicas,
                    url,
                )

            console.print(table)
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to list services: {error_detail}",
                subject="Service List Failed",
                log_message=f"Service list failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list services.",
            details={"error": str(e)},
        )
