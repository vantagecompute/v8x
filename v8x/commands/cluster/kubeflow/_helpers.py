# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared helpers for Kubeflow CLI commands."""

import urllib.parse

import httpx
import typer
from vantage_sdk.cluster.application.service_workflow import service_workflow_sdk
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


async def build_vdeployer_settings(ctx: typer.Context, cluster) -> dict:
    """Build the vdeployer settings payload from cluster creation parameters."""
    creation_params = getattr(cluster, "creation_parameters", {}) or {}
    settings = dict(creation_params.get("settings", {}))
    return await service_workflow_sdk.build_vdeployer_settings(
        ctx,
        cluster=cluster,
        settings=settings,
    )


def get_auth_headers(ctx: typer.Context) -> dict[str, str]:
    """Get authorization headers, refreshing the token if expired."""
    from v8x.deployment_apps.common import get_auth_headers as _get_auth_headers

    return _get_auth_headers(ctx)


def get_http_client() -> httpx.AsyncClient:
    """Create an httpx async client with standard timeout."""
    return httpx.AsyncClient(timeout=VDEPLOYER_TIMEOUT)
