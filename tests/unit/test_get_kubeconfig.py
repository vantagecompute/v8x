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

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from v8x.commands.get_kubeconfig import _run_get_kubeconfig
from v8x.exceptions import Abort


class StubAsyncClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self):
        """Return the stub client from the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Do not suppress exceptions raised inside the async context."""
        return False

    async def get(self, url, headers=None, params=None):
        self.calls.append({"url": url, "headers": headers, "params": params})
        return self.response


def _ctx(*, json_output: bool = False):
    ctx = MagicMock()
    ctx.obj = SimpleNamespace(
        json_output=json_output,
        settings=SimpleNamespace(vantage_url="https://app.vantagecompute.ai"),
        persona=SimpleNamespace(token_set=SimpleNamespace(access_token="token")),
    )
    return ctx


def test_run_get_kubeconfig_prints_plaintext(monkeypatch):
    ctx = _ctx(json_output=False)
    cluster = SimpleNamespace(client_id="cluster-123")
    client = StubAsyncClient(
        httpx.Response(
            200,
            text="apiVersion: v1\nkind: Config\n",
            headers={"X-Vantage-Namespace": "vantage-kubeflow-alice"},
        )
    )

    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.cluster_sdk.get_cluster_by_name",
        AsyncMock(return_value=cluster),
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.get_auth_headers",
        lambda _ctx: {"Authorization": "Bearer token"},
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.httpx.AsyncClient",
        lambda timeout: client,
    )

    with patch("typer.echo") as mock_echo:
        asyncio.run(_run_get_kubeconfig(ctx, cluster_name="test-cluster", namespace=None))

    mock_echo.assert_called_once_with("apiVersion: v1\nkind: Config\n", nl=False)
    assert client.calls == [
        {
            "url": "https://cluster-123.clusters.vantagecompute.ai/vdeployer/kubeconfig",
            "headers": {"Authorization": "Bearer token"},
            "params": None,
        }
    ]


def test_run_get_kubeconfig_passes_explicit_namespace_and_json(monkeypatch):
    ctx = _ctx(json_output=True)
    cluster = SimpleNamespace(client_id="cluster-123")
    client = StubAsyncClient(
        httpx.Response(
            200,
            text="clusters: []\n",
            headers={"X-Vantage-Namespace": "custom-ns"},
        )
    )

    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.cluster_sdk.get_cluster_by_name",
        AsyncMock(return_value=cluster),
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.get_auth_headers",
        lambda _ctx: {"Authorization": "Bearer token"},
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.httpx.AsyncClient",
        lambda timeout: client,
    )

    with patch("builtins.print") as mock_print:
        asyncio.run(_run_get_kubeconfig(ctx, cluster_name="test-cluster", namespace="custom-ns"))

    assert client.calls == [
        {
            "url": "https://cluster-123.clusters.vantagecompute.ai/vdeployer/kubeconfig",
            "headers": {"Authorization": "Bearer token"},
            "params": {"namespace": "custom-ns"},
        }
    ]
    payload = json.loads(mock_print.call_args.args[0])
    assert payload == {
        "cluster": "test-cluster",
        "namespace": "custom-ns",
        "kubeconfig": "clusters: []\n",
    }


def test_run_get_kubeconfig_404_raises_abort(monkeypatch):
    ctx = _ctx(json_output=False)
    cluster = SimpleNamespace(client_id="cluster-123")
    client = StubAsyncClient(httpx.Response(404, text="not found"))

    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.cluster_sdk.get_cluster_by_name",
        AsyncMock(return_value=cluster),
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.get_auth_headers",
        lambda _ctx: {"Authorization": "Bearer token"},
    )
    monkeypatch.setattr(
        "v8x.commands.get_kubeconfig.httpx.AsyncClient",
        lambda timeout: client,
    )

    with pytest.raises(Abort) as exc_info:
        asyncio.run(_run_get_kubeconfig(ctx, cluster_name="test-cluster", namespace="custom-ns"))

    assert "custom-ns" in str(exc_info.value)
