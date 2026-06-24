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

from v8x.deployment_apps.crud import DeploymentAppSDK


def test_builtin_lxd_extension_apps_are_discovered():
    sdk = DeploymentAppSDK()

    juju_ext = sdk.get("juju-ext", cloud="lxd")

    assert juju_ext is not None
    assert juju_ext.name == "juju-ext"
    assert juju_ext.cloud == "lxd"
    assert juju_ext.module is not None
    assert hasattr(juju_ext.module, "create")


def test_builtin_on_prem_slurm_apps_are_discovered():
    sdk = DeploymentAppSDK()

    multipass_app = sdk.get("slurm-multipass", cloud="on_prem")

    assert multipass_app is not None
    assert multipass_app.substrate == "multipass"
    assert multipass_app.module is not None
    assert hasattr(multipass_app.module, "create")


def test_builtin_on_prem_slurm_juju_app_is_discovered():
    sdk = DeploymentAppSDK()

    juju_app = sdk.get("slurm-juju", cloud="on_prem")

    assert juju_app is not None
    assert juju_app.name == "slurm-juju"
    assert juju_app.cloud == "on_prem"
    assert juju_app.substrate == "juju"
    assert juju_app.module is not None
    assert hasattr(juju_app.module, "create")
