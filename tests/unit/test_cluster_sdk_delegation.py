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

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench._vdeployer import ClusterServiceResponse

from v8x.commands.cluster.compute_pool.create import create_compute_pool
from v8x.commands.cluster.compute_pool.delete import delete_compute_pool
from v8x.commands.cluster.compute_pool.list import list_compute_pools
from v8x.commands.cluster.inference_endpoint.create import create_inference
from v8x.commands.cluster.inference_endpoint.list import list_inferences
from v8x.commands.cluster.kubeflow.create import create_kubeflow
from v8x.commands.cluster.kubeflow.delete import delete_kubeflow
from v8x.commands.cluster.kubeflow.get import get_kubeflow
from v8x.commands.cluster.model_registry.create import create_model
from v8x.commands.cluster.model_registry.search import search_models
from v8x.commands.cluster.namespace.create import create_namespace
from v8x.commands.cluster.namespace.delete import delete_namespace
from v8x.commands.cluster.namespace.list import list_namespaces
from v8x.commands.cluster.network._helpers import parse_ipam_type
from v8x.commands.cluster.network.create import create_network
from v8x.commands.cluster.network.delete import delete_network
from v8x.commands.cluster.network.get import get_network
from v8x.commands.cluster.network.list import list_networks
from v8x.commands.cluster.network.update import update_network
from v8x.commands.cluster.secret.create import create_secret
from v8x.commands.cluster.secret.delete import delete_secret
from v8x.commands.cluster.secret.get import get_secret
from v8x.commands.cluster.secret.list import list_secrets
from v8x.commands.cluster.secret.test import test_secret as secret_test_command
from v8x.commands.cluster.service.create import create_user_service
from v8x.commands.cluster.service.delete import delete_user_service
from v8x.commands.cluster.service.disable import disable_service
from v8x.commands.cluster.service.enable import enable_service
from v8x.commands.cluster.service.get import get_user_service
from v8x.commands.cluster.service.list import list_user_services
from v8x.commands.cluster.service.update import update_service
from v8x.commands.cluster.slurm.create import create_slurm_cluster
from v8x.commands.cluster.slurm.delete import delete_slurm_cluster
from v8x.commands.cluster.slurm.deploy import deploy_slurm_cluster
from v8x.commands.cluster.slurm.get import get_slurm_cluster
from v8x.commands.cluster.slurm.list import list_slurm_clusters
from v8x.commands.cluster.slurm.update import update_slurm_cluster
from v8x.commands.cluster.update import update_cluster as update_cluster_command
from v8x.commands.cluster.workspace_preset.create import create_workspace_preset
from v8x.commands.cluster.workspace_preset.delete import delete_workspace_preset
from v8x.commands.cluster.workspace_preset.get import get_workspace_preset
from v8x.commands.cluster.workspace_preset.list import list_workspace_presets


def _unwrap_command(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def test_network_ipam_type_rejects_legacy_values() -> None:
    with pytest.raises(Abort, match="Invalid IPAM type"):
        parse_ipam_type("whereabouts")
    with pytest.raises(Abort, match="Invalid IPAM type"):
        parse_ipam_type("host-local")


def _ctx(*, json_output: bool = False):
    console = SimpleNamespace(print=MagicMock())
    formatter = SimpleNamespace(
        render_error=MagicMock(), success=MagicMock(), render_update=MagicMock()
    )
    return SimpleNamespace(
        obj=SimpleNamespace(
            console=console,
            formatter=formatter,
            json_output=json_output,
            settings=SimpleNamespace(vantage_url="https://app.vantagecompute.ai"),
            persona=SimpleNamespace(token_set=SimpleNamespace(access_token="token")),
        )
    )


@pytest.mark.asyncio
async def test_create_inference_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={"kind": "predictive", "url": "https://demo", "status": {"phase": "Ready"}},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.inference_endpoint.create.inference_endpoint_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_inference)(
        ctx,
        name="demo-endpoint",
        cluster_name="cluster-a",
        model_id="model-123",
    )

    sdk_create.assert_awaited_once()
    assert sdk_create.await_args.kwargs == {
        "cluster_name": "cluster-a",
        "name": "demo-endpoint",
        "kind": "predictive",
        "model_source_type": "model_registry",
        "model_id": "model-123",
        "storage_uri": None,
        "image": None,
        "sizing_preset": None,
        "configuration_preset": None,
        "compute_pool": None,
        "cpu": None,
        "memory": None,
        "gpu_count": None,
        "framework": None,
        "credentials_secret": None,
        "overrides": None,
    }
    ctx.obj.console.print.assert_any_call(
        "[green]✓[/green] Inference endpoint 'demo-endpoint' created"
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_inferences_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data=[{"name": "demo-endpoint", "kind": "predictive"}],
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.inference_endpoint.list.inference_endpoint_sdk.list",
        sdk_list,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(list_inferences)(ctx, cluster_name="cluster-a")

    sdk_list.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    assert json.loads(mock_print.call_args.args[0]) == [
        {"name": "demo-endpoint", "kind": "predictive"}
    ]
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_model_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"job_id": "job-1", "status": "PENDING"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.model_registry.create.model_registry_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_model)(
        ctx,
        name="gemma-4b",
        version="v1",
        cluster_name="cluster-a",
        repo_id="google/gemma-4b-it",
    )

    sdk_create.assert_awaited_once()
    assert sdk_create.await_args.kwargs == {
        "cluster_name": "cluster-a",
        "name": "gemma-4b",
        "version": "v1",
        "source_type": "huggingface",
        "repo_id": "google/gemma-4b-it",
        "storage_uri": None,
        "source_url": None,
        "revision": "main",
        "description": None,
        "overwrite": False,
        "sync": False,
        "token_secret_name": None,
    }
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Model onboarding started")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_search_models_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_search = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"items": [{"id": "google/gemma-4b-it", "downloads": 42}]},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.model_registry.search.model_registry_sdk.search",
        sdk_search,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(search_models)(ctx, query="gemma", cluster_name="cluster-a")

    sdk_search.assert_awaited_once_with(ctx, cluster_name="cluster-a", query="gemma", limit=10)
    assert json.loads(mock_print.call_args.args[0]) == [
        {"id": "google/gemma-4b-it", "downloads": 42}
    ]
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_namespace_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={"name": "team-a", "labels": {"env": "dev"}},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.namespace.create.namespace_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_namespace)(
        ctx,
        name="team-a",
        cluster_name="cluster-a",
        labels_json='{"env": "dev"}',
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="team-a",
        labels={"env": "dev"},
    )
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Namespace 'team-a' created")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_namespaces_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data=[{"name": "team-a", "status": "Active"}],
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.namespace.list.namespace_sdk.list",
        sdk_list,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(list_namespaces)(ctx, cluster_name="cluster-a")

    sdk_list.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    assert json.loads(mock_print.call_args.args[0]) == [{"name": "team-a", "status": "Active"}]
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_namespace_delegates_to_sdk_with_force(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(status_code=204, data=None, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.namespace.delete.namespace_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_namespace)(
        ctx,
        name="team-a",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="team-a")
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Namespace 'team-a' deleted")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_network_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={
                "name": "data-net",
                "network_type": "ipvlan",
                "iface_name": "net1",
                "ipam": {"ip_range": "10.20.0.11-10.20.0.254/24", "gateway": "10.20.0.1"},
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.network.create.network_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_network)(
        ctx,
        name="data-net",
        cluster_name="cluster-a",
        network_type="ipvlan",
        iface_name="net1",
        bridge="br0",
        vlan=120,
        mtu=9000,
        ipam_type="nv-ipam",
        ip_range="10.20.0.0/24",
        gateway="10.20.0.1",
        exclude=["10.20.0.0/28"],
        route=['{"dst":"10.30.0.0/16"}'],
        per_node_block_size=32,
    )

    sdk_create.assert_awaited_once()
    assert sdk_create.await_args.kwargs["cluster_name"] == "cluster-a"
    network = sdk_create.await_args.kwargs["network"]
    assert network.name == "data-net"
    assert network.network_type == "ipvlan"
    assert network.iface_name == "net1"
    assert network.bridge == "br0"
    assert network.vlan == 120
    assert network.mtu == 9000
    assert network.ipam.ipam_type == "nv-ipam"
    assert network.ipam.ip_range == "10.20.0.0/24"
    assert network.ipam.gateway == "10.20.0.1"
    assert network.ipam.exclude == ["10.20.0.0/28"]
    assert network.ipam.routes == [{"dst": "10.30.0.0/16"}]
    assert network.ipam.per_node_block_size == 32
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Network 'data-net' created")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_networks_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"items": [{"name": "data-net", "network_type": "macvlan"}]},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.network.list.network_sdk.list",
        sdk_list,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(list_networks)(ctx, cluster_name="cluster-a")

    sdk_list.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    assert json.loads(mock_print.call_args.args[0]) == [
        {"name": "data-net", "network_type": "macvlan"}
    ]
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_network_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"name": "data-net", "network_type": "macvlan"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.network.get.network_sdk.get",
        sdk_get,
    )

    await _unwrap_command(get_network)(ctx, name="data-net", cluster_name="cluster-a")

    sdk_get.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="data-net")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_update_network_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_update = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"name": "data-net", "mtu": 9000},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.network.update.network_sdk.update",
        sdk_update,
    )

    await _unwrap_command(update_network)(
        ctx,
        name="data-net",
        cluster_name="cluster-a",
        network_type=None,
        iface_name=None,
        bridge=None,
        vlan=None,
        mtu=9000,
        ipam_type=None,
        ip_range="10.20.0.0/24",
        gateway="10.20.0.1",
        exclude=None,
        route=None,
        per_node_block_size=None,
    )

    sdk_update.assert_awaited_once()
    assert sdk_update.await_args.kwargs["cluster_name"] == "cluster-a"
    assert sdk_update.await_args.kwargs["name"] == "data-net"
    patch_model = sdk_update.await_args.kwargs["patch"]
    assert patch_model.mtu == 9000
    assert patch_model.ipam is not None
    assert patch_model.ipam.ipam_type == "nv-ipam"
    assert patch_model.ipam.ip_range == "10.20.0.0/24"
    assert patch_model.ipam.gateway == "10.20.0.1"
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Network 'data-net' updated")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_network_delegates_to_sdk_with_force(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(status_code=204, data=None, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.network.delete.network_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_network)(
        ctx,
        name="data-net",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="data-net")
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Network 'data-net' deleted")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_compute_pool_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={"name": "desktop-lg", "min_size": 1, "max_size": 3, "instance_type": "lg"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.compute_pool.create.compute_pool_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_compute_pool)(
        ctx,
        name="desktop-lg",
        cluster_name="cluster-a",
        instance_type="lg",
        workload="remote-desktop",
        min_size=1,
        max_size=3,
        gpu=True,
        gpu_count=1,
        control_plane=False,
        root_disk_size=200,
        labels_json='{"custom": "true"}',
        taint=["dedicated=desktop:NoSchedule"],
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="desktop-lg",
        instance_type="lg",
        min_size=1,
        max_size=3,
        gpu=True,
        gpu_count=1,
        control_plane=False,
        root_disk_size=200,
        labels={"custom": "true"},
        taints=[{"key": "dedicated", "value": "desktop", "effect": "NoSchedule"}],
        workload="remote-desktop",
    )
    ctx.obj.console.print.assert_any_call(
        "[green]✓[/green] Compute pool [green]'desktop-lg'[/green] created"
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_compute_pools_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data=[
                {
                    "name": "desktop-lg",
                    "instance_type": "lg",
                    "min_size": 1,
                    "max_size": 3,
                    "labels": {"vc.workload-type": "remote-desktop"},
                    "is_gpu": True,
                    "gpu_count": 1,
                }
            ],
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.compute_pool.list.compute_pool_sdk.list",
        sdk_list,
    )

    await _unwrap_command(list_compute_pools)(
        ctx,
        cluster_name="cluster-a",
        workload="remote-desktop",
    )

    sdk_list.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        workload="remote-desktop",
    )
    ctx.obj.console.print.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_compute_pool_delegates_to_sdk_with_force(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"message": "Compute pool 'desktop-lg' deleted"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.compute_pool.delete.compute_pool_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_compute_pool)(
        ctx,
        name="desktop-lg",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="desktop-lg")
    ctx.obj.console.print.assert_any_call("[green]✓[/green] Compute pool 'desktop-lg' deleted")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_service_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    ctx.obj.persona.identity_data = SimpleNamespace(username="alice")
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "id": "svc-1",
                "url": "https://desktop",
                "status": "Running",
                "sizing_preset": "desktop-lg",
                "configuration_preset": "desktop-lg",
                "options": {"image": "turbovnc:noble-3.3-0.2", "resolution": "2560x1440"},
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.create.user_service_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_user_service)(
        ctx,
        workload="remote-desktop",
        cluster_name="cluster-a",
        name=None,
        preset="desktop-lg",
        configuration_preset="desktop-lg",
        image="noble-3.3-0.2",
        resolution="2560x1440",
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        workload="remote-desktop",
        name=None,
        sizing_preset="desktop-lg",
        configuration_preset="desktop-lg",
        image="noble-3.3-0.2",
        resolution="2560x1440",
    )
    ctx.obj.formatter.success.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_service_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"workload": "cloud-shell", "id": "svc-1", "name": "shell"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.get.user_service_sdk.get",
        sdk_get,
    )

    await _unwrap_command(get_user_service)(
        ctx,
        workload="cloud-shell",
        service_id="svc-1",
        cluster_name="cluster-a",
    )

    sdk_get.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        workload="cloud-shell",
        service_id="svc-1",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_user_services_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    ctx.obj.persona.identity_data = SimpleNamespace(username="alice")
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "services": [
                    {
                        "workload": "cloud-shell",
                        "id": "svc-1",
                        "username": "alice",
                        "status": "Running",
                        "sizing_preset": "shell-sm",
                    }
                ],
                "count": 1,
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.list.user_service_sdk.list",
        sdk_list,
    )

    await _unwrap_command(list_user_services)(
        ctx,
        cluster_name="cluster-a",
        workload="cloud-shell",
        username=None,
        all_users=False,
    )

    sdk_list.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        workload="cloud-shell",
        username="alice",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_user_service_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"success": True},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.delete.user_service_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_user_service)(
        ctx,
        workload="pvc-viewer",
        service_id="svc-1",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        workload="pvc-viewer",
        service_id="svc-1",
    )
    ctx.obj.formatter.success.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_enable_service_delegates_to_workflow_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="cluster-a"),
        settings={"jupyterhub_enabled": False, "locked_services": []},
    )
    get_cluster_settings = AsyncMock(return_value=workflow_ctx)
    update_cluster_mock = AsyncMock(return_value=SimpleNamespace(name="cluster-a"))
    trigger_deploy = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "OK"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.enable.service_workflow_sdk.get_cluster_settings",
        get_cluster_settings,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.enable.cluster_sdk.update_cluster",
        update_cluster_mock,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.enable.service_workflow_sdk.trigger_deploy",
        trigger_deploy,
    )

    await _unwrap_command(enable_service)(ctx, service="jupyterhub", cluster_name="cluster-a")

    get_cluster_settings.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    update_cluster_mock.assert_awaited_once_with(
        ctx,
        name="cluster-a",
        settings={"jupyterhub_enabled": True, "locked_services": []},
    )
    trigger_deploy.assert_awaited_once_with(
        ctx,
        cluster=workflow_ctx.cluster,
        settings={"jupyterhub_enabled": True, "locked_services": []},
        target_component="jupyterhub",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_update_service_delegates_to_workflow_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="cluster-a"),
        settings={"mlflow_enabled": True},
    )
    get_cluster_settings = AsyncMock(return_value=workflow_ctx)
    trigger_deploy = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "OK"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.update.service_workflow_sdk.get_cluster_settings",
        get_cluster_settings,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.update.service_workflow_sdk.trigger_deploy",
        trigger_deploy,
    )

    await _unwrap_command(update_service)(ctx, service="mlflow", cluster_name="cluster-a")

    get_cluster_settings.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    trigger_deploy.assert_awaited_once_with(
        ctx,
        cluster=workflow_ctx.cluster,
        settings={"mlflow_enabled": True},
        target_component="mlflow",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_disable_service_delegates_to_workflow_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="cluster-a"),
        settings={"ray_enabled": True, "locked_services": []},
    )
    get_cluster_settings = AsyncMock(return_value=workflow_ctx)
    update_cluster_mock = AsyncMock(return_value=SimpleNamespace(name="cluster-a"))
    trigger_deploy = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "OK"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.get_cluster_settings",
        get_cluster_settings,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
        update_cluster_mock,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.trigger_deploy",
        trigger_deploy,
    )

    await _unwrap_command(disable_service)(
        ctx, service="ray", cluster_name="cluster-a", force=False
    )

    update_cluster_mock.assert_awaited_once_with(
        ctx,
        name="cluster-a",
        settings={"ray_enabled": False, "locked_services": []},
    )
    trigger_deploy.assert_awaited_once_with(
        ctx,
        cluster=workflow_ctx.cluster,
        settings={"ray_enabled": False, "locked_services": []},
        target_component="ray",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_disable_service_force_delete_delegates_to_workflow_sdk(
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="cluster-a"),
        settings={"slurm_enabled": True, "locked_services": []},
    )
    get_cluster_settings = AsyncMock(return_value=workflow_ctx)
    update_cluster_mock = AsyncMock(return_value=SimpleNamespace(name="cluster-a"))
    delete_namespace = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "started"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.get_cluster_settings",
        get_cluster_settings,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
        update_cluster_mock,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.delete_namespace",
        delete_namespace,
    )

    await _unwrap_command(disable_service)(
        ctx, service="slurm", cluster_name="cluster-a", force=True
    )

    update_cluster_mock.assert_awaited_once_with(
        ctx,
        name="cluster-a",
        settings={"slurm_enabled": False, "locked_services": []},
    )
    delete_namespace.assert_awaited_once_with(
        ctx,
        cluster=workflow_ctx.cluster,
        namespace="slurm",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_disable_service_heavy_cascade_delegates_to_workflow_sdk(
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _ctx()
    workflow_ctx = SimpleNamespace(
        cluster=SimpleNamespace(name="cluster-a"),
        settings={"kubeflow_enabled": True, "locked_services": []},
    )
    cascade_result = SimpleNamespace(
        already_disabled=False,
        job_id="job-1",
        logs=["step 1", "step 2"],
        report={"crds_deleted": 2},
        state="succeeded",
        error=None,
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.get_cluster_settings",
        AsyncMock(return_value=workflow_ctx),
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.cluster_sdk.update_cluster",
        AsyncMock(return_value=SimpleNamespace(name="cluster-a")),
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.service.disable.service_workflow_sdk.run_heavy_cascade",
        AsyncMock(return_value=cascade_result),
    )

    await _unwrap_command(disable_service)(
        ctx,
        service="kubeflow",
        cluster_name="cluster-a",
        force=True,
    )

    ctx.obj.console.print.assert_any_call("step 1")
    ctx.obj.console.print.assert_any_call("step 2")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_cluster_update_triggers_workflow_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    cluster_with_settings = SimpleNamespace(client_id="client-1")
    merged_settings = {"autoscaler_enabled": True}
    monkeypatch.setattr(
        "v8x.commands.cluster.update._merge_and_validate_settings",
        AsyncMock(return_value=(cluster_with_settings, merged_settings)),
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.update.cluster_sdk.update_cluster",
        AsyncMock(
            return_value=SimpleNamespace(
                name="cluster-a",
                status="ready",
                client_id="client-1",
                description="desc",
                owner_email="user@example.com",
                cluster_type="k8s",
                cloud_account_id=1,
                creation_parameters={"settings": merged_settings},
                cluster_type_display="K8s",
                is_ready=True,
                jupyterhub_url=None,
            )
        ),
    )
    trigger = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "OK"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.update.service_workflow_sdk.trigger_deploy",
        trigger,
    )

    await _unwrap_command(update_cluster_command)(
        ctx,
        cluster_name="cluster-a",
        description=None,
        status=None,
        settings='{"autoscaler_enabled": true}',
        settings_file=None,
        config=None,
        config_file=None,
        merge=False,
    )

    trigger.assert_awaited_once_with(
        ctx,
        cluster=cluster_with_settings,
        settings=merged_settings,
        target_component="",
    )
    ctx.obj.formatter.render_update.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_kubeflow_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "started"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.kubeflow.create.kubeflow_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_kubeflow)(
        ctx,
        cluster_name="cluster-a",
        admin_node_group="kubeflow-admin",
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        admin_node_group="kubeflow-admin",
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_kubeflow_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(status_code=200, data={"message": "started"}, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.kubeflow.delete.kubeflow_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_kubeflow)(ctx, cluster_name="cluster-a", yes=True)

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_kubeflow_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "status": "running",
                "deployed": True,
                "namespace": "kubeflow",
                "pod_count": 5,
                "components": {"centraldashboard": True},
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.kubeflow.get.kubeflow_sdk.get",
        sdk_get,
    )

    await _unwrap_command(get_kubeflow)(ctx, cluster_name="cluster-a")

    sdk_get.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    ctx.obj.console.print.assert_called()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_slurm_cluster_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=SimpleNamespace(
            registration={"clientId": "slurm-client", "clientSecret": "super-secret-token-value"},
            response=ClusterServiceResponse(
                status_code=200,
                data={"message": "Slurm deployment started"},
                text="",
            ),
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.create.slurm_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_slurm_cluster)(
        ctx,
        name="hpc-prod",
        cluster_name="cluster-a",
        control_node_group="slurm-admin",
        partition=["cpu:slurm-compute:default"],
        exposed=True,
        tls_enabled=True,
        profiling=True,
        bridge=True,
        slurmctld_lb_ip="192.168.8.221",
        slurmdbd_lb_ip=None,
        slurmrestd_lb_ip=None,
        influxdb_lb_ip=None,
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="hpc-prod",
        control_node_group="slurm-admin",
        partition_specs=["cpu:slurm-compute:default"],
        exposed=True,
        tls_enabled=True,
        profiling=True,
        bridge=True,
        slurmctld_lb_ip="192.168.8.221",
        slurmdbd_lb_ip=None,
        slurmrestd_lb_ip=None,
        influxdb_lb_ip=None,
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_deploy_slurm_cluster_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_deploy = AsyncMock(
        return_value=SimpleNamespace(
            registration={"clientId": "slurm-client", "clientSecret": "secret"},
            response=ClusterServiceResponse(
                status_code=200,
                data={"message": "Slurm deployment started"},
                text="",
            ),
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.deploy.slurm_sdk.deploy",
        sdk_deploy,
    )

    await _unwrap_command(deploy_slurm_cluster)(
        ctx,
        name="hpc-prod",
        cluster_name="cluster-a",
        control_node_group="slurm-admin",
        partition=["cpu:slurm-compute:default"],
        exposed=False,
        tls_enabled=True,
        profiling=True,
        bridge=True,
    )

    sdk_deploy.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="hpc-prod",
        control_node_group="slurm-admin",
        partition_specs=["cpu:slurm-compute:default"],
        exposed=False,
        tls_enabled=True,
        profiling=True,
        bridge=True,
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_slurm_cluster_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "name": "hpc-prod",
                "namespace": "slurm-hpc-prod",
                "status": "running",
                "controller_ready": True,
                "accounting_ready": True,
                "restapi_ready": False,
                "node_count": 4,
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.get.slurm_sdk.get",
        sdk_get,
    )

    await _unwrap_command(get_slurm_cluster)(ctx, name="hpc-prod", cluster_name="cluster-a")

    sdk_get.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="hpc-prod")
    ctx.obj.console.print.assert_called()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_slurm_clusters_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "clusters": [
                    {
                        "name": "hpc-prod",
                        "namespace": "slurm-hpc-prod",
                        "status": "running",
                        "controller_ready": True,
                        "accounting_ready": True,
                        "restapi_ready": False,
                        "node_count": 4,
                    }
                ]
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.list.slurm_sdk.list",
        sdk_list,
    )

    await _unwrap_command(list_slurm_clusters)(ctx, cluster_name="cluster-a")

    sdk_list.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    ctx.obj.console.print.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_update_slurm_cluster_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_update = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"message": "Slurm cluster update started"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.update.slurm_sdk.update",
        sdk_update,
    )

    await _unwrap_command(update_slurm_cluster)(
        ctx,
        name="hpc-prod",
        cluster_name="cluster-a",
        exposed=True,
        tls_enabled=False,
        profiling=True,
        bridge=False,
    )

    sdk_update.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="hpc-prod",
        exposed=True,
        tls_enabled=False,
        profiling=True,
        bridge=False,
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_slurm_cluster_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=SimpleNamespace(
            response=ClusterServiceResponse(
                status_code=200,
                data={"message": "Slurm cluster deletion started"},
                text="",
            ),
            api_result={"message": "API registration removed"},
            api_error=None,
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.slurm.delete.slurm_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_slurm_cluster)(
        ctx,
        name="hpc-prod",
        cluster_name="cluster-a",
        yes=True,
    )

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="hpc-prod")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_secret_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={"namespace": "profile-alice"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.secret.create.secret_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_secret)(
        ctx,
        name="hf-token",
        cluster_name="cluster-a",
        secret_type="huggingface",
        value="hf_xxx",
        access_key_id=None,
        secret_access_key=None,
        region=None,
        endpoint_url=None,
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="hf-token",
        secret_type="huggingface",
        value="hf_xxx",
        access_key_id=None,
        secret_access_key=None,
        region=None,
        endpoint_url=None,
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_secret_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"name": "hf-token", "type": "huggingface"},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.secret.get.secret_sdk.get",
        sdk_get,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(get_secret)(ctx, name="hf-token", cluster_name="cluster-a")

    sdk_get.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="hf-token")
    assert json.loads(mock_print.call_args.args[0]) == {"name": "hf-token", "type": "huggingface"}
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_secrets_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"items": [{"name": "hf-token", "type": "huggingface"}]},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.secret.list.secret_sdk.list",
        sdk_list,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(list_secrets)(
            ctx, cluster_name="cluster-a", secret_type="huggingface"
        )

    sdk_list.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        secret_type="huggingface",
    )
    assert json.loads(mock_print.call_args.args[0]) == [
        {"name": "hf-token", "type": "huggingface"}
    ]
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_secret_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(status_code=204, data=None, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.secret.delete.secret_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_secret)(
        ctx,
        name="hf-token",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="hf-token")
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_test_secret_delegates_to_sdk_for_json_output(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(json_output=True)
    sdk_test = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={"ok": True, "bucket_count": 3},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.secret.test.secret_sdk.test",
        sdk_test,
    )

    with patch("builtins.print") as mock_print:
        await _unwrap_command(secret_test_command)(ctx, name="my-s3", cluster_name="cluster-a")

    sdk_test.assert_awaited_once_with(ctx, cluster_name="cluster-a", name="my-s3")
    assert json.loads(mock_print.call_args.args[0]) == {"ok": True, "bucket_count": 3}
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_create_workspace_preset_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_create = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=201,
            data={"metadata": {"name": "platform-jupyterlab"}},
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.workspace_preset.create.workspace_preset_sdk.create",
        sdk_create,
    )

    await _unwrap_command(create_workspace_preset)(
        ctx,
        display_name="JupyterLab",
        cluster_name="cluster-a",
        description="",
        ide_type="codeserver",
        pod_sizes_json='[{"display_name": "sm"}]',
        home_pvc="user-homes",
        hidden=True,
    )

    sdk_create.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        display_name="JupyterLab",
        description="",
        ide_type="codeserver",
        pod_sizes=[{"display_name": "sm"}],
        home_pvc="user-homes",
        hidden=True,
    )
    ctx.obj.console.print.assert_any_call(
        "[green]✓[/green] Workspace preset [green]'platform-jupyterlab'[/green] created"
    )
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_get_workspace_preset_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_get = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data={
                "name": "platform-jupyterlab",
                "display_name": "JupyterLab",
                "description": "Default IDE",
                "ide_type": "JUPYTERLAB",
                "home_pvc": "user-homes",
            },
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.workspace_preset.get.workspace_preset_sdk.get",
        sdk_get,
    )

    await _unwrap_command(get_workspace_preset)(
        ctx,
        name="platform-jupyterlab",
        cluster_name="cluster-a",
    )

    sdk_get.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="platform-jupyterlab",
    )
    ctx.obj.console.print.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_list_workspace_presets_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx()
    sdk_list = AsyncMock(
        return_value=ClusterServiceResponse(
            status_code=200,
            data=[
                {
                    "name": "platform-jupyterlab",
                    "display_name": "JupyterLab",
                    "ide_type": "JUPYTERLAB",
                    "hidden": False,
                    "deprecated": False,
                }
            ],
            text="",
        )
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.workspace_preset.list.workspace_preset_sdk.list",
        sdk_list,
    )

    await _unwrap_command(list_workspace_presets)(ctx, cluster_name="cluster-a")

    sdk_list.assert_awaited_once_with(ctx, cluster_name="cluster-a")
    ctx.obj.console.print.assert_called_once()
    ctx.obj.formatter.render_error.assert_not_called()


@pytest.mark.asyncio
async def test_delete_workspace_preset_delegates_to_sdk_with_force(
    monkeypatch: pytest.MonkeyPatch,
):
    ctx = _ctx()
    sdk_delete = AsyncMock(
        return_value=ClusterServiceResponse(status_code=204, data=None, text="")
    )
    monkeypatch.setattr(
        "v8x.commands.cluster.workspace_preset.delete.workspace_preset_sdk.delete",
        sdk_delete,
    )

    await _unwrap_command(delete_workspace_preset)(
        ctx,
        name="platform-jupyterlab",
        cluster_name="cluster-a",
        force=True,
    )

    sdk_delete.assert_awaited_once_with(
        ctx,
        cluster_name="cluster-a",
        name="platform-jupyterlab",
    )
    ctx.obj.console.print.assert_any_call(
        "[green]✓[/green] Workspace preset 'platform-jupyterlab' deleted"
    )
    ctx.obj.formatter.render_error.assert_not_called()
