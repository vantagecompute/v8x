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
"""Shared helpers for compute-pool CLI commands."""

import urllib.parse

import httpx
import typer
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

VDEPLOYER_TIMEOUT = 30.0


def get_vdeployer_web_url(client_id: str, vantage_url: str) -> str:
    """Construct the vdeployer-web base URL from client_id and vantage_url."""
    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    base_domain = hostname.removeprefix("app.")
    return f"https://{client_id}.clusters.{base_domain}/vdeployer"


async def get_cluster_with_creds(ctx: typer.Context, cluster_name: str):
    """Fetch a cluster with full credentials."""
    cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
    if not cluster:
        raise Abort(
            f"Cluster '{cluster_name}' not found.",
            subject="Cluster Not Found",
            log_message=f"Cluster '{cluster_name}' not found",
        )
    return cluster


def get_auth_headers(ctx: typer.Context) -> dict[str, str]:
    """Get authorization headers, refreshing the token if expired."""
    from v8x.deployment_apps.common import get_auth_headers as _get_auth_headers

    return _get_auth_headers(ctx)


def get_http_client() -> httpx.AsyncClient:
    """Create an httpx async client with standard timeout."""
    return httpx.AsyncClient(timeout=VDEPLOYER_TIMEOUT)
