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

import asyncio
from typing import Any, Dict

import httpx
import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.commands.cluster.utils import (
    build_vdeployer_settings,
    get_vdeployer_web_url,
    resolve_provider,
    send_vdeployer_request,
    validate_cluster_credentials,
)
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

# Valid services that can be enabled/disabled
VALID_SERVICES = {"slurm", "jupyterhub", "kubeflow", "mlflow", "ray"}

# Services for which `disable --force` runs the new heavy-cleanup cascade
# (vdeployer-web /disable-service/{name} endpoint with SSE log tail).
# Other services keep the legacy --force path (DELETE /namespace/{name}).
SERVICES_WITH_HEAVY_CASCADE = {"kubeflow"}


async def _handle_force_delete(
    ctx,
    console,
    cluster,
    service_lower: str,
    existing_settings: Dict[str, Any],
    setting_key: str,
) -> None:
    """Handle force deletion of a service namespace.

    Updates the cluster settings to mark the service as disabled, then
    sends a DELETE request to vdeployer-web to force-remove the namespace.

    Args:
        ctx: Typer context
        console: Rich console for output
        cluster: Cluster object with credentials
        service_lower: Lowercase service name
        existing_settings: Current cluster settings dict (modified in place)
        setting_key: Settings key to disable (e.g., 'slurm_enabled')
    """
    console.print(f"[bold red]Force deleting {service_lower} namespace...[/bold red]")

    # Update DB to mark service as disabled
    existing_settings[setting_key] = False
    await cluster_sdk.update_cluster(
        ctx,
        name=cluster.name,
        settings=existing_settings,
    )
    console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")

    # Send DELETE request to force-delete namespace
    vdeployer_url = get_vdeployer_web_url(
        client_id=cluster.client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )
    result = await send_vdeployer_request(
        console, "DELETE", f"{vdeployer_url}/namespace/{service_lower}"
    )
    if result:
        console.print(
            f"[green]✓[/green] Force delete of '{service_lower}' started: {result.get('message', 'OK')}"
        )


async def _run_heavy_cascade(
    ctx,
    console,
    cluster,
    service_lower: str,
    existing_settings: Dict[str, Any],
    setting_key: str,
) -> None:
    """Heavy disable cascade — DB flag flip + new endpoint + SSE log tail + report."""
    console.print(f"[bold red]Disabling {service_lower} (heavy cascade)...[/bold red]")

    # 1) DB flag flip — same as the legacy --force path
    existing_settings[setting_key] = False
    await cluster_sdk.update_cluster(
        ctx,
        name=cluster.name,
        settings=existing_settings,
    )
    console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")

    # 2) Trigger the cascade
    vdeployer_url = get_vdeployer_web_url(
        client_id=cluster.client_id,
        vantage_url=ctx.obj.settings.vantage_url,
    )
    auth = {"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
        post = await client.post(
            f"{vdeployer_url}/disable-service/{service_lower}",
            headers=auth,
        )
        if post.status_code == 410:
            console.print(f"[green]✓[/green] {service_lower} already cleanly disabled (no-op)")
            return
        if post.status_code == 403:
            raise Abort(
                "vdeployer-web returned 403 — `disable-service` requires the "
                "vantage-admin role on your token. Re-login as an admin or have "
                "an admin run the command.",
                subject="Admin role required",
                log_message=f"403 on disable-service/{service_lower}",
            )
        if post.status_code == 409:
            raise Abort(
                "Another disable / deploy is already in progress on this cluster. "
                "Wait for it to finish, then retry.",
                subject="Concurrent operation",
                log_message=f"409 on disable-service/{service_lower}",
            )
        if post.status_code == 404:
            raise Abort(
                "vdeployer-web returned 404 — this cluster's vdeployer-web is "
                "older than the disable-service endpoint. Update the cluster's "
                "vdeployer-web image and retry.",
                subject="Endpoint not available",
                log_message=f"404 on disable-service/{service_lower}",
            )
        post.raise_for_status()
        job = post.json()

        # 3) Stream cascade output via SSE
        # logs_url / status_url are absolute paths from the server root
        # (e.g. "/vdeployer/disable-service/kubeflow/logs"), so we build the
        # full URL using only the scheme+host from vdeployer_url.
        parsed = httpx.URL(vdeployer_url)
        base_host = f"{parsed.scheme}://{parsed.host}"
        if parsed.port:
            base_host = f"{base_host}:{parsed.port}"
        console.print(f"[dim]job_id: {job['job_id']}; tailing logs...[/dim]\n")
        async for line in _tail_sse(client, f"{base_host}{job['logs_url']}", auth):
            console.print(line)

        # 4) Fetch final report
        status_resp = await client.get(
            f"{base_host}{job['status_url']}",
            headers=auth,
        )
        status_resp.raise_for_status()
        status = status_resp.json()

    _print_report(console, status, service_lower)
    if status.get("state") != "succeeded":
        raise Abort(
            f"Cascade did not succeed: {status.get('error') or 'see logs above'}",
            subject="Disable failed",
            log_message=f"cascade state={status.get('state')}",
        )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def disable_service(
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

    # Validate service name
    service_lower = service.lower()
    if service_lower not in VALID_SERVICES:
        raise Abort(
            f"Invalid service '{service}'. Valid services: {', '.join(sorted(VALID_SERVICES))}",
            subject="Invalid Service",
            log_message=f"Invalid service: {service}",
        )

    setting_key = f"{service_lower}_enabled"
    verbose = getattr(ctx.obj, "verbose", False)

    try:
        # IMPORTANT: Use get_cluster_by_name to get FULL settings including sensitive fields.
        # The regular get() query may filter out certs/keys.
        # Since the backend REPLACES settings (not merges), we must send back
        # all existing settings with our change merged in.
        cluster_with_creds = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
        if not cluster_with_creds:
            raise Abort(
                f"Cluster '{cluster_name}' not found.",
                subject="Cluster Not Found",
                log_message=f"Cluster '{cluster_name}' not found",
            )

        # Get existing settings (full, including sensitive fields)
        creation_params = cluster_with_creds.creation_parameters or {}
        existing_settings: Dict[str, Any] = dict(creation_params.get("settings", {}))

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

        # Heavy-cascade services (kubeflow): require --force confirmation.
        if service_lower in SERVICES_WITH_HEAVY_CASCADE:
            if not force:
                raise Abort(
                    f"'disable {service_lower}' deletes user data + CRDs and must be "
                    "confirmed. Re-run with --force.",
                    subject="Confirmation required",
                    log_message=f"disable {service_lower} attempted without --force",
                )
            await _run_heavy_cascade(
                ctx, console, cluster_with_creds, service_lower, existing_settings, setting_key
            )
            return

        # Legacy --force path for other services.
        if force:
            await _handle_force_delete(
                ctx, console, cluster_with_creds, service_lower, existing_settings, setting_key
            )
            return

        # Check if already disabled (normal path)
        if existing_settings.get(setting_key, False) is False:
            console.print(
                f"[yellow]Service '{service_lower}' is already disabled on cluster '{cluster_name}'[/yellow]"
            )
            return

        # Merge our change into the full settings
        # Backend REPLACES settings, so we must send the complete merged set
        existing_settings[setting_key] = False

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

        console.print(f"[dim]Updated cluster settings: {setting_key}=false[/dim]")
        console.print("[dim]Triggering vdeployer-web update...[/dim]")

        # Validate credentials and resolve provider
        validate_cluster_credentials(cluster_with_creds)
        provider = await resolve_provider(ctx, cluster_with_creds)

        # Build and send vdeployer-web deploy request
        vdeployer_settings = build_vdeployer_settings(
            existing_settings, provider, cluster_with_creds, ctx.obj.persona
        )
        vdeployer_url = get_vdeployer_web_url(
            client_id=cluster_with_creds.client_id,
            vantage_url=ctx.obj.settings.vantage_url,
        )
        result = await send_vdeployer_request(
            console,
            "PUT",
            f"{vdeployer_url}/deploy",
            json_data={"settings": vdeployer_settings, "target_component": service_lower},
            headers={"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"},
        )
        if result:
            console.print(
                f"[green]✓[/green] Service '{service_lower}' disabled on cluster '{cluster_name}': {result.get('message', 'OK')}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"An unexpected error occurred while disabling '{service}' on cluster '{cluster_name}'.",
            details={"error": str(e)},
        )


def _print_report(console, status: Dict[str, Any], service_lower: str) -> None:
    """Print the structured cleanup report from a successful cascade."""
    report = status.get("report") or {}
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


async def _tail_sse(client, url, headers):
    """Yield each `data: ...` line from an SSE stream until `event: done` arrives.

    Retries up to 3 times with exponential backoff on 404 — handles the race
    where the CLI POSTs and immediately tries to subscribe to logs before
    the background task has registered the buffer.
    """
    backoff = 0.25
    for attempt in range(4):
        async with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code == 404 and attempt < 3:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            async for raw in resp.aiter_lines():
                if raw.startswith("data: "):
                    yield raw[6:]
                elif raw.startswith("event: done"):
                    return
            return
