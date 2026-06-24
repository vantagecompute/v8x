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

import pytest
import yaml
from vantage_sdk.exceptions import Abort

from v8x.apps.on_prem.slurm_juju import utils as juju_utils
from v8x.apps.on_prem.slurm_juju.constants import CLUSTER_SECRET_CONSUMERS, LDAP_PORT
from v8x.apps.on_prem.slurm_juju.schema import SlurmJujuOptions
from v8x.commands.cluster.create import _parse_slurm_juju_options


def test_parse_slurm_juju_options_parses_controller_and_model() -> None:
    options = _parse_slurm_juju_options("controller=lxd-controller,model=hpc")

    assert isinstance(options, SlurmJujuOptions)
    assert options.controller == "lxd-controller"
    assert options.model == "hpc"
    assert options.model_target == "lxd-controller:hpc"


def test_parse_slurm_juju_options_requires_both_keys() -> None:
    with pytest.raises(Abort):
        _parse_slurm_juju_options("controller=lxd-controller")


def test_parse_slurm_juju_options_rejects_empty_options() -> None:
    with pytest.raises(Abort):
        _parse_slurm_juju_options(None)


def test_parse_slurm_juju_options_rejects_unknown_key() -> None:
    with pytest.raises(Abort):
        _parse_slurm_juju_options("controller=c,model=m,gpu=1")


def test_parse_slurm_juju_options_rejects_invalid_juju_name() -> None:
    with pytest.raises(Abort):
        _parse_slurm_juju_options("controller=Bad_Name,model=hpc")


def test_derive_ldap_uri_appends_port() -> None:
    assert (
        juju_utils.derive_ldap_uri("ldaps://openldap.dev.vantagecompute.ai", LDAP_PORT)
        == "ldaps://openldap.dev.vantagecompute.ai:636"
    )


def test_render_bundle_injects_derived_ldap_uri() -> None:
    rendered = juju_utils.render_bundle(ldap_uri="ldaps://openldap.dev.vantagecompute.ai:636")
    data = yaml.safe_load(rendered)

    assert "applications" in data
    assert (
        data["applications"]["sssd"]["options"]["ldap-uri"]
        == "ldaps://openldap.dev.vantagecompute.ai:636"
    )


def test_bundle_application_names_includes_secret_consumers() -> None:
    names = juju_utils.bundle_application_names()

    assert "slurmctld" in names
    for consumer in CLUSTER_SECRET_CONSUMERS:
        assert consumer in names


def test_check_juju_available_raises_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(juju_utils.shutil, "which", lambda _binary: None)
    with pytest.raises(Abort):
        juju_utils.check_juju_available()


def test_redact_for_log_masks_secret_values() -> None:
    args = [
        "add-secret",
        "-m",
        "lxd:hpc",
        "vantage-cluster",
        "vantage-url=https://app.dev.vantagecompute.ai",
        "client-id=abc-123",
        "client-secret=super-secret-value",
        "org-id=org-uuid",
        "ldap-bind-password=s3cr3t-pw",
    ]
    redacted = juju_utils._redact_for_log(args)

    joined = " ".join(redacted)
    # Sensitive values must not appear; their keys remain visible.
    assert "super-secret-value" not in joined
    assert "s3cr3t-pw" not in joined
    assert "abc-123" not in joined
    assert "client-secret=***" in redacted
    assert "ldap-bind-password=***" in redacted
    # Non-sensitive values are preserved.
    assert "vantage-url=https://app.dev.vantagecompute.ai" in redacted
    assert "org-id=org-uuid" in redacted
