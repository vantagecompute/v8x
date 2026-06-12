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
"""Tests for the heavy-cascade flow in v8x cluster service disable."""

from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import patch as _patch

import httpx as _real_httpx
import pytest
import respx

from v8x.commands.cluster.service.disable import (
    SERVICES_WITH_HEAVY_CASCADE,
    _tail_sse,
    disable_service,
)
from v8x.exceptions import Abort

# The conftest mock_graphql_client fixture globally patches httpx.AsyncClient.
# These tests need the real httpx.AsyncClient so respx transport-level mocking works.
_real_async_client = _real_httpx.AsyncClient


def test_services_with_heavy_cascade_includes_kubeflow():
    assert "kubeflow" in SERVICES_WITH_HEAVY_CASCADE


@pytest.mark.asyncio
async def test_disable_kubeflow_without_force_aborts():
    """`disable kubeflow` without --force must abort with a confirmation message."""
    ctx = MagicMock()
    ctx.obj.console = MagicMock()
    ctx.obj.verbose = False

    fake_cluster = MagicMock()
    fake_cluster.creation_parameters = {"settings": {"kubeflow_enabled": True}}
    with patch(
        "v8x.commands.cluster.service.disable.cluster_sdk.get_cluster_by_name",
        new=AsyncMock(return_value=fake_cluster),
    ):
        # Unwrap the 4 decorators to call the underlying coroutine directly.
        # The decorators applied are (outer to inner):
        #   @handle_abort -> @attach_settings -> @attach_persona -> @attach_vantage_rest_client
        # Each uses @wraps so __wrapped__ gives us the next level down.
        with pytest.raises(Abort) as exc_info:
            await disable_service.__wrapped__.__wrapped__.__wrapped__.__wrapped__(
                ctx=ctx,
                service="kubeflow",
                cluster_name="test-cluster",
                force=False,
            )

    assert "force" in str(exc_info.value).lower() or "confirm" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tail_sse_yields_data_lines_until_done():
    """SSE body yields each `data:` line until `event: done`."""
    sse_body = (
        "data: line one\n\n"
        "data: line two\n\n"
        "data: line three\n\n"
        "event: done\ndata: cascade complete\n\n"
    )
    with _patch("httpx.AsyncClient", _real_async_client):
        async with respx.mock as router:
            router.get("https://example/logs").mock(
                return_value=_real_httpx.Response(200, content=sse_body.encode())
            )
            async with _real_async_client() as client:
                lines = []
                async for line in _tail_sse(client, "https://example/logs", {}):
                    lines.append(line)

    assert lines == ["line one", "line two", "line three"]


@pytest.mark.asyncio
async def test_tail_sse_retries_on_404():
    """SSE endpoint 404 (race: cascade not started yet) retries with backoff."""
    call_count = {"n": 0}

    with _patch("httpx.AsyncClient", _real_async_client):
        async with respx.mock as router:

            def _handler(request):
                call_count["n"] += 1
                if call_count["n"] < 2:
                    return _real_httpx.Response(404, text="not yet")
                return _real_httpx.Response(200, content=b"data: ok\n\nevent: done\n\n")

            router.get("https://example/logs").mock(side_effect=_handler)

            async with _real_async_client() as client:
                lines = []
                async for line in _tail_sse(client, "https://example/logs", {}):
                    lines.append(line)

    assert lines == ["ok"]
    assert call_count["n"] == 2  # one 404 + one success


def test_print_report_formats_counters_and_strip_audit():
    from v8x.commands.cluster.service.disable import _print_report

    console = MagicMock()
    status = {
        "report": {
            "workspaces_deleted": 5,
            "workspace_kinds_deleted": 2,
            "profile_namespaces_deleted": 3,
            "system_namespaces_deleted": 4,
            "crds_deleted": 13,
            "node_groups_deleted": 2,
            "finalizers_stripped": [
                "workspaces.kubeflow.org/team-a/ws-1",
                "namespace/vantage-kubeflow-team-b",
            ],
        }
    }

    _print_report(console, status, "kubeflow")

    rendered = "\n".join(call.args[0] for call in console.print.call_args_list if call.args)
    assert "Cleanup report" in rendered
    assert "workspaces deleted:         5" in rendered
    assert "node groups deleted:        2" in rendered
    assert "finalizers stripped:        2" in rendered
    assert "workspaces.kubeflow.org/team-a/ws-1" in rendered


def test_print_report_handles_missing_report_gracefully():
    from v8x.commands.cluster.service.disable import _print_report

    console = MagicMock()
    _print_report(console, {"report": None}, "kubeflow")
    assert console.print.call_count == 0


@pytest.mark.asyncio
async def test_run_heavy_cascade_happy_path_streams_logs_then_prints_report():
    """POST 202 + SSE log tail + status=succeeded — cascade completes without raising."""
    from v8x.commands.cluster.service.disable import _run_heavy_cascade

    ctx = MagicMock()
    ctx.obj.persona.token_set.access_token = "test-token"
    ctx.obj.settings.vantage_url = "https://vantage.test"
    console = MagicMock()
    cluster = MagicMock()
    cluster.client_id = "client-id-123"
    cluster.name = "test-cluster"
    existing_settings = {"kubeflow_enabled": True}

    job_body = {
        "job_id": "kubeflow-disable-1",
        "status": "accepted",
        "message": "kubeflow disable cascade started",
        "logs_url": "/vdeployer/disable-service/kubeflow/logs",
        "status_url": "/vdeployer/disable-service/kubeflow/status",
    }
    sse_body = "data: step 1 done\n\ndata: step 2 done\n\nevent: done\n\n"
    status_body = {
        "job_id": "kubeflow-disable-1",
        "state": "succeeded",
        "started_at": "2026-05-03T12:00:00Z",
        "finished_at": "2026-05-03T12:05:00Z",
        "report": {
            "success": True,
            "workspaces_deleted": 3,
            "finalizers_stripped": [],
            "errors": [],
        },
        "error": None,
    }

    with (
        _patch(
            "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
            new=AsyncMock(),
        ),
        _patch(
            "v8x.commands.cluster.service.disable.get_vdeployer_web_url",
            return_value="https://vdeployer.test/vdeployer",
        ),
        _patch("httpx.AsyncClient", _real_async_client),
    ):
        async with respx.mock as router:
            router.post("https://vdeployer.test/vdeployer/disable-service/kubeflow").mock(
                return_value=_real_httpx.Response(202, json=job_body)
            )
            router.get("https://vdeployer.test/vdeployer/disable-service/kubeflow/logs").mock(
                return_value=_real_httpx.Response(200, content=sse_body.encode())
            )
            router.get("https://vdeployer.test/vdeployer/disable-service/kubeflow/status").mock(
                return_value=_real_httpx.Response(200, json=status_body)
            )

            await _run_heavy_cascade(
                ctx, console, cluster, "kubeflow", existing_settings, "kubeflow_enabled"
            )

    # The flag flip happened
    assert existing_settings["kubeflow_enabled"] is False
    rendered = "\n".join(c.args[0] for c in console.print.call_args_list if c.args)
    assert "Cleanup report — kubeflow" in rendered


@pytest.mark.asyncio
async def test_run_heavy_cascade_403_aborts_with_admin_guidance():
    from v8x.commands.cluster.service.disable import _run_heavy_cascade

    ctx = MagicMock()
    ctx.obj.persona.token_set.access_token = "test-token"
    ctx.obj.settings.vantage_url = "https://vantage.test"
    console = MagicMock()
    cluster = MagicMock()
    cluster.client_id = "client-id-123"
    cluster.name = "test-cluster"

    with (
        _patch(
            "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
            new=AsyncMock(),
        ),
        _patch(
            "v8x.commands.cluster.service.disable.get_vdeployer_web_url",
            return_value="https://vdeployer.test/vdeployer",
        ),
        _patch("httpx.AsyncClient", _real_async_client),
    ):
        async with respx.mock as router:
            router.post("https://vdeployer.test/vdeployer/disable-service/kubeflow").mock(
                return_value=_real_httpx.Response(403, text="forbidden")
            )

            with pytest.raises(Abort) as exc_info:
                await _run_heavy_cascade(
                    ctx,
                    console,
                    cluster,
                    "kubeflow",
                    {},
                    "kubeflow_enabled",
                )

    assert "admin" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_run_heavy_cascade_410_returns_no_op_message():
    """410 means already cleanly disabled — print no-op message and return."""
    from v8x.commands.cluster.service.disable import _run_heavy_cascade

    ctx = MagicMock()
    ctx.obj.persona.token_set.access_token = "test-token"
    ctx.obj.settings.vantage_url = "https://vantage.test"
    console = MagicMock()
    cluster = MagicMock()
    cluster.client_id = "client-id-123"
    cluster.name = "test-cluster"

    with (
        _patch(
            "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
            new=AsyncMock(),
        ),
        _patch(
            "v8x.commands.cluster.service.disable.get_vdeployer_web_url",
            return_value="https://vdeployer.test/vdeployer",
        ),
        _patch("httpx.AsyncClient", _real_async_client),
    ):
        async with respx.mock as router:
            router.post("https://vdeployer.test/vdeployer/disable-service/kubeflow").mock(
                return_value=_real_httpx.Response(410, json={"detail": "already disabled"})
            )

            await _run_heavy_cascade(
                ctx,
                console,
                cluster,
                "kubeflow",
                {},
                "kubeflow_enabled",
            )

    rendered = "\n".join(c.args[0] for c in console.print.call_args_list if c.args)
    assert "already" in rendered.lower()
