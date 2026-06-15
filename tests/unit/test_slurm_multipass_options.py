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

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest
from vantage_sdk.exceptions import Abort

from v8x.apps.on_prem.slurm_multipass import app as multipass_app
from v8x.apps.on_prem.slurm_multipass import constants as multipass_constants
from v8x.commands.cluster.create import (
    SLURM_MULTIPASS_OPTIONS_HELP,
    _parse_slurm_multipass_options,
    create_cluster,
)


def _cloud_init_for_operating_system(recorded: dict, operating_system: str) -> tuple[str, str]:
    recorded["operating_system"] = operating_system
    return "#cloud-config", f"https://example.com/{operating_system}.img"


def test_parse_slurm_multipass_options_normalizes_example_values() -> None:
    assert _parse_slurm_multipass_options(
        "operating_system=rockylinux9,cpu=4,mem=8,disk=128G",
        "slurm-multipass",
    ) == {
        "operating_system": "rockylinux9",
        "cpu": "4",
        "mem": "8GB",
        "disk": "128GB",
    }


@pytest.mark.parametrize(
    "operating_system",
    multipass_constants.SUPPORTED_MULTIPASS_OPERATING_SYSTEMS,
)
def test_parse_slurm_multipass_options_accepts_supported_operating_systems(
    operating_system: str,
) -> None:
    assert _parse_slurm_multipass_options(
        f"operating_system={operating_system}",
        "slurm-multipass",
    ) == {"operating_system": operating_system}


def test_parse_slurm_multipass_options_rejects_unsupported_operating_system() -> None:
    with pytest.raises(Abort, match="Unsupported operating_system"):
        _parse_slurm_multipass_options(
            "operating_system=jammy",
            "slurm-multipass",
        )


def test_multipass_image_name_rejects_unsupported_operating_system() -> None:
    with pytest.raises(ValueError, match="Unsupported Multipass operating system"):
        multipass_constants.get_multipass_cloud_image_name("jammy")


def test_cluster_create_options_help_shows_operating_system_choices() -> None:
    command = create_cluster
    while hasattr(command, "__wrapped__"):
        command = command.__wrapped__

    options_parameter = inspect.signature(command).parameters["options"]
    option_info = get_args(options_parameter.annotation)[1]

    assert option_info.help == SLURM_MULTIPASS_OPTIONS_HELP
    for operating_system in multipass_constants.SUPPORTED_MULTIPASS_OPERATING_SYSTEMS:
        assert operating_system in option_info.help


def test_parse_slurm_multipass_options_rejects_other_apps() -> None:
    with pytest.raises(Abort):
        _parse_slurm_multipass_options("cpu=4", "vantage-system")


def test_parse_slurm_multipass_options_rejects_unknown_keys() -> None:
    with pytest.raises(Abort):
        _parse_slurm_multipass_options(
            "gpu=1",
            "slurm-multipass",
        )


def test_launch_vm_instance_uses_resource_overrides(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeProcess:
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

        def communicate(self, input=None):
            captured["input"] = input
            return b"", b""

    monkeypatch.setattr(multipass_app.subprocess, "Popen", FakeProcess)

    multipass_app._launch_vm_instance(
        instance_name="demo",
        shared_dir=tmp_path,
        cloud_init_config="#cloud-config",
        image_origin="https://example.com/rockylinux9.img",
        cpu="4",
        memory="8GB",
        disk="128GB",
    )

    assert captured["cmd"] == [
        "multipass",
        "launch",
        "-c4",
        "-m8GB",
        "-d128GB",
        "--mount",
        f"{tmp_path}:/shared",
        "-n",
        "demo",
        "--cloud-init",
        "-",
        "https://example.com/rockylinux9.img",
    ]
    assert captured["input"] == b"#cloud-config"


def test_multipass_image_origin_uses_templated_remote_name(monkeypatch, tmp_path: Path) -> None:
    image_name = multipass_constants.get_multipass_cloud_image_name("rockylinux9")
    monkeypatch.setattr(
        multipass_app, "MULTIPASS_CLOUD_IMAGE_BASE_URL", "https://example.com/images"
    )
    monkeypatch.setattr(
        multipass_app,
        "MULTIPASS_CLOUD_IMAGE_LOCAL",
        tmp_path / "build" / multipass_constants.get_multipass_cloud_image_name("resolute"),
    )
    monkeypatch.setattr(
        multipass_app,
        "MULTIPASS_CLOUD_IMAGE_DEST",
        tmp_path / "tmp" / multipass_constants.get_multipass_cloud_image_name("resolute"),
    )

    assert multipass_app._multipass_image_origin("rockylinux9") == (
        f"https://example.com/images/{image_name}"
    )


def test_multipass_image_origin_checks_templated_local_image(monkeypatch, tmp_path: Path) -> None:
    image_name = multipass_constants.get_multipass_cloud_image_name("rockylinux10")
    local_image = tmp_path / "build" / image_name
    local_image.parent.mkdir()
    local_image.touch()
    monkeypatch.setattr(
        multipass_app, "MULTIPASS_CLOUD_IMAGE_LOCAL", local_image.parent / "unused.img"
    )
    monkeypatch.setattr(
        multipass_app, "MULTIPASS_CLOUD_IMAGE_DEST", tmp_path / "tmp" / "unused.img"
    )

    assert multipass_app._multipass_image_origin("rockylinux10") == f"file://{local_image}"


def test_create_uses_slurm_multipass_options(monkeypatch, tmp_path: Path) -> None:
    recorded = {}
    cluster = SimpleNamespace(
        name="demo",
        client_id="client-id",
        client_secret="client-secret",
        sssd_binder_password="binder-password",
        creation_parameters={"jupyterhub_token": "jupyterhub-token"},
    )
    ctx = SimpleNamespace(
        obj=SimpleNamespace(
            console=SimpleNamespace(print=lambda *args, **kwargs: None),
            verbose=False,
            settings=SimpleNamespace(
                get_apis_url=lambda: "https://apis.example.com",
                get_auth_url=lambda: "https://auth.example.com",
                get_tunnel_url=lambda: "https://tunnel.example.com",
                get_ldap_url=lambda: "ldap://ldap.example.com",
                oidc_domain="auth.example.com/realms/vantage",
            ),
            persona=SimpleNamespace(identity_data=SimpleNamespace(org_id="org-123")),
            slurm_multipass_options={
                "operating_system": "rockylinux9",
                "cpu": "4",
                "mem": "8GB",
                "disk": "128GB",
            },
        )
    )
    deployment = SimpleNamespace(
        id="deployment-id",
        name="deployment-demo",
        cluster=cluster,
        status="initializing",
        write=lambda: None,
    )

    monkeypatch.setattr(multipass_app, "check_multipass_available", lambda: None)
    monkeypatch.setattr(multipass_app.cloud_sdk, "get", lambda name: SimpleNamespace(name=name))
    monkeypatch.setattr(
        multipass_app,
        "create_deployment_with_init_status",
        lambda **kwargs: deployment,
    )
    monkeypatch.setattr(
        multipass_app, "_prepare_shared_directory", lambda verbose, console: tmp_path
    )
    monkeypatch.setattr(
        multipass_app,
        "_generate_cloud_init_configuration",
        lambda vantage_cluster_ctx, operating_system: _cloud_init_for_operating_system(
            recorded,
            operating_system,
        ),
    )

    def fake_launch(instance_name, shared_dir, cloud_init_config, image_origin, cpu, memory, disk):
        recorded.update(
            {
                "instance_name": instance_name,
                "shared_dir": shared_dir,
                "cloud_init_config": cloud_init_config,
                "image_origin": image_origin,
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
            }
        )

    monkeypatch.setattr(multipass_app, "_launch_vm_instance", fake_launch)

    exit_result = asyncio.run(multipass_app.create(ctx=ctx, cluster=cluster))

    assert exit_result.exit_code == 0
    assert recorded == {
        "operating_system": "rockylinux9",
        "instance_name": "deployment-demo",
        "shared_dir": tmp_path,
        "cloud_init_config": "#cloud-config",
        "image_origin": "https://example.com/rockylinux9.img",
        "cpu": "4",
        "memory": "8GB",
        "disk": "128GB",
    }
    assert deployment.status == "active"
