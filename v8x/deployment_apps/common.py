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
"""Common utilities for deployment apps."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
import typer
from vantage_sdk.cloud.schema import Cloud
from vantage_sdk.cluster.schema import Cluster, VantageClusterContext
from vantage_sdk.exceptions import Abort

from v8x.deployment_apps.constants import (
    DEV_CLIENT_ID,
    DEV_CLIENT_SECRET,
    DEV_JUPYTERHUB_TOKEN,
    DEV_SSSD_BINDER_PASSWORD,
)
from v8x.deployments.crud import deployment_sdk
from v8x.deployments.schema import Deployment


def generate_dev_cluster_data(cluster_name: Optional[str] = None) -> Cluster:
    """Generate dummy cluster data for development/testing purposes."""
    return Cluster(
        name=f"dev-cluster-{cluster_name or ''}",
        client_id=DEV_CLIENT_ID,
        client_secret=DEV_CLIENT_SECRET,
        status="dev",
        description=f"Development cluster {cluster_name or ''}",
        owner_email="dev@localhost",
        cluster_type="slurm",
        cloud_account_id=None,
        creation_parameters={
            "jupyterhub_token": DEV_JUPYTERHUB_TOKEN,
        },
        sssd_binder_password=DEV_SSSD_BINDER_PASSWORD,
    )


def create_deployment_with_init_status(
    app_name: str,
    cluster: Cluster,
    vantage_cluster_ctx: VantageClusterContext,
    cloud: Cloud,
    substrate: str,
    cloud_account_id: Optional[int] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
    k8s_namespaces: Optional[List[str]] = None,
    verbose: bool = False,
) -> Deployment:
    """Create a new deployment with 'init' status immediately after dependency checks."""
    return deployment_sdk.create_deployment(
        app_name=app_name,
        cluster=cluster,
        vantage_cluster_ctx=vantage_cluster_ctx,
        cloud=cloud,
        cloud_account_id=cloud_account_id,
        substrate=substrate,
        status="init",
        additional_metadata=additional_metadata or {},
        k8s_namespaces=k8s_namespaces or [],
        verbose=verbose,
    )


logger = logging.getLogger(__name__)


def _get_profile(ctx: typer.Context) -> str:
    """Extract the profile name from the CLI context."""
    return getattr(ctx.obj.settings, "profile", "default")


def get_auth_headers(ctx: typer.Context) -> dict[str, str]:
    """Get authorization headers, refreshing the token if expired."""
    from v8x.auth import refresh_token_if_needed

    refresh_token_if_needed(_get_profile(ctx), ctx.obj.persona.token_set)
    return {"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"}


async def wait_for_vdeployer_web_ready(
    ctx: typer.Context,
    client_id: str,
    vantage_url: str,
    timeout_seconds: int = 1000,
    poll_interval: int = 5,
) -> None:
    """Wait for vdeployer-web to be ready by polling its health endpoint."""
    console = ctx.obj.console

    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    base_domain = hostname.removeprefix("app.")
    health_url = f"https://{client_id}.clusters.{base_domain}/vdeployer/status"

    console.print(
        f"[dim]Waiting for vdeployer-web to be ready (timeout: {timeout_seconds}s)...[/dim]"
    )
    console.print(f"[dim]  Health endpoint: {health_url}[/dim]")

    elapsed = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        while elapsed < timeout_seconds:
            try:
                headers = get_auth_headers(ctx)
            except Abort:
                console.print(
                    "[bold yellow]⚠ Authentication expired during health check loop. "
                    "Please log in again.[/bold yellow]"
                )
                from v8x.auth import fetch_auth_tokens, init_persona
                from v8x.cache import save_tokens_to_cache

                token_set = await fetch_auth_tokens(ctx.obj)
                save_tokens_to_cache(ctx.obj.profile, token_set)
                init_persona(ctx, token_set)
                console.print("[green]✓[/green] Re-authenticated successfully, resuming...")
                headers = get_auth_headers(ctx)

            try:
                response = await client.get(health_url, headers=headers)
                if response.status_code == 200:
                    console.print("[green]✓[/green] vdeployer-web is ready")
                    return
                else:
                    console.print(
                        f"[dim]  Health check returned {response.status_code}, retrying... ({elapsed}/{timeout_seconds}s)[/dim]"
                    )
            except httpx.ConnectError:
                console.print(
                    f"[dim]  Connection refused, tunnel not ready yet... ({elapsed}/{timeout_seconds}s)[/dim]"
                )
            except httpx.TimeoutException:
                console.print(
                    f"[dim]  Request timed out, retrying... ({elapsed}/{timeout_seconds}s)[/dim]"
                )
            except Abort:
                raise
            except Exception as e:
                console.print(
                    f"[dim]  Error: {e}, retrying... ({elapsed}/{timeout_seconds}s)[/dim]"
                )
                logger.debug(f"Health check error: {e}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    raise Exception(f"Timeout waiting for vdeployer-web after {timeout_seconds}s")