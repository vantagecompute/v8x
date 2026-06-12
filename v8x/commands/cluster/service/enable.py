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
"""Enable service command for v8x."""

from typing import Any, Dict

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.application.service_workflow import VALID_SERVICES, service_workflow_sdk
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def enable_service(
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Argument(
            help=f"Service to enable. Valid services: {', '.join(sorted(VALID_SERVICES))}"
        ),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the cluster to update",
        ),
    ],
):
    """Enable a service on a Vantage cluster.

    This command updates the cluster settings to enable the specified service
    and triggers vdeployer to reconcile the cluster state.

    Examples:
        # Enable JupyterHub on a cluster
        v8x cluster service enable jupyterhub --cluster my-cluster

        # Enable Slurm
        v8x cluster service enable slurm -c my-cluster

        # Enable MLflow
        v8x cluster service enable mlflow --cluster my-cluster
    """
    console = ctx.obj.console

    service_lower = service_workflow_sdk.normalize_service(service)

    setting_key = f"{service_lower}_enabled"
    verbose = getattr(ctx.obj, "verbose", False)

    try:
        # IMPORTANT: Use get_cluster_by_name to get FULL settings including sensitive fields.
        # The regular get() query may filter out certs/keys.
        # Since the backend REPLACES settings (not merges), we must send back
        # all existing settings with our change merged in.
        workflow_ctx = await service_workflow_sdk.get_cluster_settings(
            ctx, cluster_name=cluster_name
        )
        cluster_with_creds = workflow_ctx.cluster
        existing_settings: Dict[str, Any] = dict(workflow_ctx.settings)

        if verbose:
            console.print(
                f"[dim]Current {setting_key}: {existing_settings.get(setting_key, False)}[/dim]"
            )
            console.print(f"[dim]Total settings keys: {len(existing_settings)}[/dim]")

        # Check if service is locked (controlled by settings file, not CLI)
        locked_services = existing_settings.get("locked_services", [])
        if service_lower in locked_services:
            console.print(
                f"[yellow]Service '{service_lower}' is locked and cannot be modified via CLI.[/yellow]\n"
                f"[dim]To change this, update the cluster settings file and redeploy.[/dim]"
            )
            return

        # Check if already enabled
        if existing_settings.get(setting_key, False) is True:
            console.print(
                f"[yellow]Service '{service_lower}' is already enabled on cluster '{cluster_name}'[/yellow]"
            )
            return

        # Merge our change into the full settings
        # Backend REPLACES settings, so we must send the complete merged set
        existing_settings[setting_key] = True

        if verbose:
            console.print(f"[dim]Sending merged settings ({len(existing_settings)} keys)[/dim]")

        # Update cluster in database via SDK
        cluster = await cluster_sdk.update_cluster(
            ctx,
            name=cluster_name,
            settings=existing_settings,
        )

        if cluster is None:
            raise Abort(
                f"Cluster '{cluster_name}' not found after update.",
                subject="Cluster Not Found",
                log_message=f"Cluster '{cluster_name}' not found after update",
            )

        console.print(f"[dim]Updated cluster settings: {setting_key}=true[/dim]")
        console.print("[dim]Triggering vdeployer-web update...[/dim]")

        response = await service_workflow_sdk.trigger_deploy(
            ctx,
            cluster=cluster_with_creds,
            settings=existing_settings,
            target_component=service_lower,
        )
        if response.status_code == 200:
            result = response.json() or {}
            console.print(
                f"[green]✓[/green] Service '{service_lower}' enabled on cluster '{cluster_name}': {result.get('message', 'OK')}"
            )
        elif response.status_code == 409:
            result = response.json() or {}
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'A task is already running')}"
            )
        else:
            console.print(
                f"[yellow]Warning:[/yellow] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"An unexpected error occurred while enabling '{service}' on cluster '{cluster_name}'.",
            details={"error": str(e)},
        )
