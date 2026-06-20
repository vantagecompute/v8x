from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from vantage_sdk.exceptions import Abort

from v8x.commands.cluster.create import deploy_app_to_cluster


def _ctx():
    return SimpleNamespace(
        obj=SimpleNamespace(
            console=SimpleNamespace(print=MagicMock()),
            verbose=False,
        )
    )


@pytest.mark.asyncio
async def test_deploy_app_to_cluster_raises_when_app_create_fails(monkeypatch):
    app = SimpleNamespace(
        name="vantage-system",
        module=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("boom"))),
    )
    monkeypatch.setattr("v8x.deployment_apps.deployment_app_sdk.get", lambda *_, **__: app)

    with pytest.raises(Abort, match="Failed to deploy app"):
        await deploy_app_to_cluster(
            _ctx(),
            SimpleNamespace(name="cluster-a"),
            "vantage-system",
            "lxd",
        )


@pytest.mark.asyncio
async def test_deploy_app_to_cluster_raises_when_app_missing(monkeypatch):
    monkeypatch.setattr("v8x.deployment_apps.deployment_app_sdk.get", lambda *_, **__: None)
    monkeypatch.setattr("v8x.deployment_apps.deployment_app_sdk.list", lambda: [])

    with pytest.raises(Abort, match="App 'missing-app' not found"):
        await deploy_app_to_cluster(
            _ctx(),
            SimpleNamespace(name="cluster-a"),
            "missing-app",
            "lxd",
        )
