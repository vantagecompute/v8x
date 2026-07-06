"""Tests for v8x LXD slurm provider command construction."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from v8x.apps.lxd.slurm import app as lxd_app


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        obj=SimpleNamespace(
            console=MagicMock(),
            settings=SimpleNamespace(vantage_url="https://app.dev.vantagecompute.ai"),
            cloud_config_metadata={
                "lxd_server_url": "https://10.0.0.10:8443",
                "lxd_client_cert": "CERT",
                "lxd_client_key": "KEY",
            },
        )
    )


def _cluster_ctx(settings: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        client_id="cluster-client",
        client_secret="cluster-secret",
        settings={
            "autoscaler_lxd_default_network": "default",
            "lxd_project_name": "vantage-system",
            **settings,
        },
    )


def test_provider_command_passes_tag_version_without_default_chart_overrides(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(lxd_app.subprocess, "run", fake_run)

    lxd_app._run_vantage_provider_provision(
        ctx=_ctx(),
        vantage_cluster_ctx=_cluster_ctx({"tag_version": "0.2"}),
        binary_path=Path("/tmp/vantage-provider"),
    )

    cmd = captured["cmd"]
    assert cmd[0:3] == ["/tmp/vantage-provider", "lxd", "provision"]
    assert cmd[cmd.index("--tag-version") + 1] == "0.2"
    assert cmd[cmd.index("--containerd-device") + 1] == (
        "/dev/disk/by-id/virtio-vantage-containerd"
    )
    assert cmd[cmd.index("--containerd-disk-size") + 1] == "100"
    assert "--vdeployer-web-chart-version" not in cmd
    assert "--vdeployer-istio-base-chart-version" not in cmd


def test_provider_command_preserves_explicit_control_plane_instance_type(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(lxd_app.subprocess, "run", fake_run)

    lxd_app._run_vantage_provider_provision(
        ctx=_ctx(),
        vantage_cluster_ctx=_cluster_ctx(
            {
                "default_control_node_groups": [
                    {"name": "control-plane", "instance_type": "control-plane-smx"}
                ]
            }
        ),
        binary_path=Path("/tmp/vantage-provider"),
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("--control-plane-instance-type") + 1] == "control-plane-smx"


def test_provider_command_preserves_explicit_chart_overrides(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(lxd_app.subprocess, "run", fake_run)

    lxd_app._run_vantage_provider_provision(
        ctx=_ctx(),
        vantage_cluster_ctx=_cluster_ctx(
            {
                "tag_version": "0.2",
                "vdeployer_web_chart_version": "0.1.676",
                "vdeployer_istio_base_chart_version": "0.1.676",
            }
        ),
        binary_path=Path("/tmp/vantage-provider"),
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("--tag-version") + 1] == "0.2"
    assert cmd[cmd.index("--vdeployer-web-chart-version") + 1] == "0.1.676"
    assert cmd[cmd.index("--vdeployer-istio-base-chart-version") + 1] == "0.1.676"


def test_provider_command_preserves_explicit_containerd_settings(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(lxd_app.subprocess, "run", fake_run)

    lxd_app._run_vantage_provider_provision(
        ctx=_ctx(),
        vantage_cluster_ctx=_cluster_ctx(
            {
                "autoscaler_lxd_containerd_device": "/dev/disk/by-id/custom-containerd",
                "autoscaler_lxd_containerd_disk_size": 250,
                "autoscaler_lxd_containerd_storage_pool": "fast-pool",
            }
        ),
        binary_path=Path("/tmp/vantage-provider"),
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("--containerd-device") + 1] == "/dev/disk/by-id/custom-containerd"
    assert cmd[cmd.index("--containerd-disk-size") + 1] == "250"
    assert cmd[cmd.index("--containerd-storage-pool") + 1] == "fast-pool"
