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
"""Disable service command for v8x."""

from typing import Any, Dict

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.application.service_workflow import (
    SERVICES_WITH_HEAVY_CASCADE,
    VALID_SERVICES,
    service_workflow_sdk,
)
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
async def disable_service(  # noqa: C901
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Argument(
            help=f"Service to disable. Valid services: {', '.join(sorted(VALID_SERVICES))}"
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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force delete the service namespace and all resources. Use when service is in a broken state.",
        ),
    ] = False,
):
    """Disable a service on a Vantage cluster.

    This command updates the cluster settings to disable the specified service
    and triggers vdeployer to reconcile the cluster state, removing the service
    components from the cluster.

    Use --force to completely wipe the service namespace when the service is in
    a broken state and normal disable doesn't work.

    Examples:
        # Disable JupyterHub on a cluster
        v8x cluster service disable jupyterhub --cluster my-cluster

        # Disable Slurm
        v8x cluster service disable slurm -c my-cluster

        # Disable MLflow
        v8x cluster service disable mlflow --cluster my-cluster

        # Force delete SLURM when it's broken
        v8x cluster service disable slurm --cluster my-cluster --force
    """
    console = ctx.obj.console
    service_lower = service_workflow_sdk.normalize_service(service)

    setting_key = f"{service_lower}_enabled"
    verbose = getattr(ctx.obj, "verbose", False)

    try:
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
        # Allow --force to bypass lock for emergency cleanup
        locked_services = existing_settings.get("locked_services", [])
        if service_lower in locked_services and not force:
            console.print(
                f"[yellow]Service '{service_lower}' is locked and cannot be modified via CLI.[/yellow]\n"
                f"[dim]To change this, update the cluster settings file and redeploy.[/dim]\n"
                f"[dim]Use --force to bypass this check for emergency cleanup.[/dim]"
            )
            return

        if service_lower in SERVICES_WITH_HEAVY_CASCADE:
            if not force:
                raise Abort(
                    f"'disable {service_lower}' deletes user data + CRDs and must be "
                    "confirmed. Re-run with --force.",
                    subject="Confirmation required",
                    log_message=f"disable {service_lower} attempted without --force",
                )

            existing_settings[setting_key] = False
            await cluster_sdk.update_cluster(
                ctx,
                name=cluster_name,
                settings=existing_settings,
            )
            console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")
            console.print(f"[bold red]Disabling {service_lower} (heavy cascade)...[/bold red]")

            cascade = await service_workflow_sdk.run_heavy_cascade(
                ctx,
                cluster=cluster_with_creds,
                service=service_lower,
            )
            if cascade.already_disabled:
                console.print(f"[green]✓[/green] {service_lower} already cleanly disabled (no-op)")
                return
            if cascade.job_id:
                console.print(f"[dim]job_id: {cascade.job_id}; streamed logs:[/dim]\n")
            for line in cascade.logs:
                console.print(line)
            _print_cascade_report(console, cascade.report or {}, service_lower)
            if cascade.state != "succeeded":
                raise Abort(
                    f"Cascade did not succeed: {cascade.error or 'see logs above'}",
                    subject="Disable failed",
                    log_message=f"cascade state={cascade.state}",
                )
            return

        if force:
            console.print(f"[bold red]Force deleting {service_lower} namespace...[/bold red]")
            existing_settings[setting_key] = False
            await cluster_sdk.update_cluster(
                ctx,
                name=cluster_name,
                settings=existing_settings,
            )
            console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")
            response = await service_workflow_sdk.delete_namespace(
                ctx,
                cluster=cluster_with_creds,
                namespace=service_lower,
            )
            if response.ok:
                result = response.json() or {}
                console.print(
                    f"[green]✓[/green] Force delete of '{service_lower}' started: {result.get('message', 'OK')}"
                )
            else:
                console.print(
                    f"[yellow]Warning:[/yellow] vdeployer-web returned {response.status_code}: {response.text}"
                )
            return

        # Check if already disabled (normal path)
        if existing_settings.get(setting_key, False) is False:
            console.print(
                f"[yellow]Service '{service_lower}' is already disabled on cluster '{cluster_name}'[/yellow]"
            )
            return

        existing_settings[setting_key] = False

        if verbose:
            console.print(f"[dim]Sending merged settings ({len(existing_settings)} keys)[/dim]")

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

        console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")
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
                f"[green]✓[/green] Service '{service_lower}' disabled on cluster '{cluster_name}': {result.get('message', 'OK')}"
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
            error_message=f"An unexpected error occurred while disabling '{service}' on cluster '{cluster_name}'.",
            details={"error": str(e)},
        )


def _print_cascade_report(console, report: Dict[str, Any], service_lower: str) -> None:
    """Print the structured cleanup report from a successful cascade."""
    if not report:
        return
    console.print(f"\n[bold]Cleanup report — {service_lower}:[/bold]")
    console.print(f"  workspaces deleted:         {report.get('workspaces_deleted', 0)}")
    console.print(f"  workspace_kinds deleted:    {report.get('workspace_kinds_deleted', 0)}")
    console.print(f"  profile namespaces deleted: {report.get('profile_namespaces_deleted', 0)}")
    console.print(f"  system namespaces deleted:  {report.get('system_namespaces_deleted', 0)}")
    console.print(f"  CRDs deleted:               {report.get('crds_deleted', 0)}")
    console.print(f"  node groups deleted:        {report.get('node_groups_deleted', 0)}")
    stripped = report.get("finalizers_stripped") or []
    if stripped:
        console.print(f"  [yellow]finalizers stripped:        {len(stripped)}[/yellow]")
        for s in stripped[:10]:
            console.print(f"    [yellow]- {s}[/yellow]")
