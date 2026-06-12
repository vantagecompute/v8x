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

"""Top-level kubeconfig retrieval command."""

from __future__ import annotations

import json

import httpx
import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.cache import with_cache
from v8x.deployment_apps.common import get_auth_headers
from v8x.commands.cluster.utils import get_vdeployer_web_url
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

VDEPLOYER_TIMEOUT = 30.0


async def _run_get_kubeconfig(
    ctx: typer.Context,
    *,
    cluster_name: str,
    namespace: str | None,
) -> None:
    cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
    if not cluster:
        raise Abort(
            f"Cluster '{cluster_name}' not found.",
            subject="Cluster Not Found",
        )

    vdeployer_url = get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)
    url = f"{vdeployer_url}/kubeconfig"
    params = {"namespace": namespace} if namespace else None

    async with httpx.AsyncClient(timeout=VDEPLOYER_TIMEOUT) as client:
        response = await client.get(url, headers=get_auth_headers(ctx), params=params)

    if response.status_code == 404:
        target = namespace or response.headers.get("X-Vantage-Namespace") or "default namespace"
        raise Abort(
            f"Kubeconfig not found for namespace '{target}' on cluster '{cluster_name}'.",
            subject="Kubeconfig Not Found",
        )
    if response.status_code != 200:
        raise Abort(
            f"Failed to get kubeconfig: {response.text}",
            subject="API Error",
        )

    resolved_ns = response.headers.get("X-Vantage-Namespace") or namespace
    if ctx.obj.json_output:
        print(
            json.dumps(
                {
                    "cluster": cluster_name,
                    "namespace": resolved_ns,
                    "kubeconfig": response.text,
                }
            )
        )
        return

    typer.echo(response.text, nl=False)


@handle_abort
@with_cache
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_kubeconfig(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the target K8s cluster"),
    ],
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Namespace to fetch from. Defaults to your user namespace when omitted.",
        ),
    ] = None,
):
    """Fetch the kubeconfig for a cluster namespace.

    Examples:
        v8x get-kubeconfig --cluster my-cluster
        v8x get-kubeconfig --cluster my-cluster --namespace custom-ns
        v8x get-kubeconfig --cluster my-cluster > kubeconfig.yaml
    """
    await _run_get_kubeconfig(ctx, cluster_name=cluster_name, namespace=namespace)
