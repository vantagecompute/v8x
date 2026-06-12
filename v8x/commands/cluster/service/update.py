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
"""Update service command for v8x."""

from typing import Any, Dict

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.application.service_workflow import VALID_SERVICES, service_workflow_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def update_service(
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Argument(
            help=f"Service to update. Valid services: {', '.join(sorted(VALID_SERVICES))}"
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
    """Update/reconcile a service on a Vantage cluster.

    This command triggers vdeployer to reconcile the specified service
    without changing any cluster settings. Use this to apply configuration
    changes or re-sync a service to its desired state.

    Examples:
        # Update JupyterHub configuration
        v8x cluster service update jupyterhub --cluster my-cluster

        # Reconcile Slurm
        v8x cluster service update slurm -c my-cluster

        # Re-sync MLflow
        v8x cluster service update mlflow --cluster my-cluster
    """
    console = ctx.obj.console

    service_lower = service_workflow_sdk.normalize_service(service)

    setting_key = f"{service_lower}_enabled"
    verbose = getattr(ctx.obj, "verbose", False)

    try:
        # Get cluster with full settings including sensitive fields
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

        # Check if the service is enabled
        if existing_settings.get(setting_key, False) is not True:
            raise Abort(
                f"Service '{service_lower}' is not enabled on cluster '{cluster_name}'. "
                f"Use 'v8x cluster service enable {service_lower}' first.",
                subject="Service Not Enabled",
                log_message=f"Service '{service_lower}' not enabled",
            )

        console.print("[dim]Triggering vdeployer-web update...[/dim]")

        response = await service_workflow_sdk.trigger_deploy(
            ctx,
            cluster=cluster_with_creds,
            settings=existing_settings,
            target_component=service_lower,
        )

        if response.status_code == 200:
            result = response.json()
            console.print(
                f"[green]✓[/green] Service '{service_lower}' update triggered on cluster '{cluster_name}': {result.get('message', 'OK')}"
            )
        elif response.status_code == 409:
            result = response.json()
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
            error_message=f"An unexpected error occurred while updating '{service}' on cluster '{cluster_name}'.",
            details={"error": str(e)},
        )
