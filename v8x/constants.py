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
"""Constants for v8x."""

from pathlib import Path

# Cloud and deployment type constants
CLOUD_LOCALHOST = "localhost"
CLOUD_AWS = "aws"
CLOUD_GCP = "gcp"
CLOUD_AZURE = "azure"
CLOUD_KUBERNETES = "kubernetes"
CLOUD_ON_PREMISES = "on-premises"

CLOUD_TYPE_K8S = "k8s"
CLOUD_TYPE_VM = "vm"
CLOUD_TYPE_CONTAINER = "container"

PROVIDER_SUBSTRATE_MULTIPASS = "multipass"
PROVIDER_SUBSTRATE_LXD = "lxd"
PROVIDER_SUBSTRATE_MICROK8S = "microk8s"

V8X_LOCAL_USER_BASE_DIR: Path = Path.home() / ".v8x"
V8X_DEV_APPS_DIR: Path = V8X_LOCAL_USER_BASE_DIR / "v8x_dev_apps"
V8X_CREDENTIALS_FILE: Path = V8X_LOCAL_USER_BASE_DIR / "credentials.yaml"
V8X_DEBUG_LOG_PATH: Path = V8X_LOCAL_USER_BASE_DIR / "debug.log"
V8X_DEPLOYMENTS_YAML_PATH: Path = V8X_LOCAL_USER_BASE_DIR / "deployments.yaml"
V8X_DEPLOYMENTS_CACHE_PATH: Path = V8X_LOCAL_USER_BASE_DIR / "deployments"
V8X_ACTIVE_PROFILE: Path = V8X_LOCAL_USER_BASE_DIR / "active_profile"

USER_CONFIG_FILE: Path = V8X_LOCAL_USER_BASE_DIR / "config.json"

USER_TOKEN_CACHE_DIR: Path = V8X_LOCAL_USER_BASE_DIR / "token_cache"

# Common deployment constants
DEFAULT_CLUSTER_NAME = "vantage-cluster"
DEFAULT_MODEL_PREFIX = "vantage"
# Multipass-specific constants


# Environment variable names
ENV_CLIENT_SECRET = "VANTAGE_CLIENT_SECRET"
ENV_OIDC_DOMAIN = "VANTAGE_OIDC_DOMAIN"
ENV_BASE_API_URL = "VANTAGE_BASE_API_URL"
ENV_TUNNEL_API_URL = "VANTAGE_TUNNEL_API_URL"

# OIDC paths
OIDC_DEVICE_PATH = "/realms/vantage/device"
OIDC_TOKEN_PATH = "/realms/vantage/protocol/openid-connect/token"

# OIDC scopes - offline_access is required to receive a refresh token
OIDC_SCOPES = "openid offline_access"

# Proactively refresh tokens this many seconds before expiry
TOKEN_REFRESH_THRESHOLD_SECONDS = 300

# Error messages
ERROR_NO_CLUSTER_DATA = "[red]Error: No cluster data provided.[/red]"
ERROR_NO_CLIENT_ID = "[red]Error: No client ID found in cluster data.[/red]"
ERROR_NO_CLIENT_SECRET = "[red]Error: No client secret found in cluster data.[/red]"
ERROR_MULTIPASS_NOT_FOUND = "[red]Error: 'multipass' is not installed or not found in PATH.[/red]"
