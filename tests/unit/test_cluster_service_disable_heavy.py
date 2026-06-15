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
"""Tests for the current v8x cluster service disable workflow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from v8x.commands.cluster.service.disable import SERVICES_WITH_HEAVY_CASCADE, disable_service
from v8x.exceptions import Abort


def _unwrap_command(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def _ctx():
    return SimpleNamespace(
        obj=SimpleNamespace(
            console=MagicMock(),
            formatter=SimpleNamespace(render_error=MagicMock()),
            verbose=False,
        )
    )


def test_services_with_heavy_cascade_includes_kubeflow():
    assert "kubeflow" in SERVICES_WITH_HEAVY_CASCADE


@pytest.mark.asyncio
async def test_disable_kubeflow_without_force_aborts(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="test-cluster"),
        settings={"kubeflow_enabled": True, "locked_services": []},
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.get_cluster_settings",
        AsyncMock(return_value=workflow_ctx),
    )

    with pytest.raises(Abort, match="force|confirmed"):
        await _unwrap_command(disable_service)(
            ctx=ctx,
            service="kubeflow",
            cluster_name="test-cluster",
            force=False,
        )


@pytest.mark.asyncio
async def test_disable_kubeflow_force_delegates_heavy_cascade(
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="test-cluster"),
        settings={"kubeflow_enabled": True, "locked_services": []},
    )
    cascade_result = SimpleNamespace(
        already_disabled=False,
        job_id="job-1",
        logs=["step 1", "step 2"],
        report={"workspaces_deleted": 3, "crds_deleted": 2},
        state="succeeded",
        error=None,
    )
    update_cluster = AsyncMock(return_value=SimpleNamespace(name="test-cluster"))
    run_heavy_cascade = AsyncMock(return_value=cascade_result)
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.get_cluster_settings",
        AsyncMock(return_value=workflow_ctx),
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
        update_cluster,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.run_heavy_cascade",
        run_heavy_cascade,
    )

    await _unwrap_command(disable_service)(
        ctx=ctx,
        service="kubeflow",
        cluster_name="test-cluster",
        force=True,
    )

    update_cluster.assert_awaited_once_with(
        ctx,
        name="test-cluster",
        settings={"kubeflow_enabled": False, "locked_services": []},
    )
    run_heavy_cascade.assert_awaited_once_with(
        ctx,
        cluster=workflow_ctx.cluster,
        service="kubeflow",
    )
    ctx.obj.console.print.assert_any_call("step 1")
    ctx.obj.console.print.assert_any_call("step 2")
    ctx.obj.formatter.render_error.assert_not_called()
