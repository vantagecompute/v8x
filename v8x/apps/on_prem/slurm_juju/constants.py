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

"""SLURM Juju on-prem deployment constants."""

# Discovery metadata read by v8x.deployment_apps.crud.DeploymentAppSDK.
# The registry key is f"{CLOUD}/{APP_NAME}" -> "on_prem/slurm-juju".
APP_NAME = "slurm-juju"
CLOUD = "on_prem"
SUBSTRATE = "juju"

# --options keys accepted for `v8x cluster create --app slurm-juju`.
# controller + model select the (pre-existing) Juju controller and model to
# deploy into. Extend this set when adding options like "slurmd-units".
SLURM_JUJU_OPTION_KEYS = {"controller", "model"}

# The one required post-deploy Juju secret (see the operators repo
# docusaurus/docs/deployment.md section 3). Shared by both consumer charms.
CLUSTER_SECRET_NAME = "vantage-cluster"
CLUSTER_SECRET_CONSUMERS = ("vantage-agent", "sssd")

# sssd application + option whose ldap-uri we derive from settings.
SSSD_APP_NAME = "sssd"
SSSD_LDAP_URI_OPTION = "ldap-uri"
# LDAPS port appended to the derived openldap host (settings.get_ldap_url()).
LDAP_PORT = 636

# Timeouts (seconds) for the juju CLI invocations.
JUJU_DEPLOY_TIMEOUT = 600
JUJU_DEFAULT_TIMEOUT = 120

# Keys stored on the deployment record so `remove` can target the same model.
META_JUJU_CONTROLLER = "juju_controller"
META_JUJU_MODEL = "juju_model"
