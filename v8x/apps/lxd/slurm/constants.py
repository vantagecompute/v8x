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
"""Constants for Vantage System on LXD deployment."""

APP_NAME = "vantage-system"
CLOUD = "lxd"
SUBSTRATE = "lxd"

DEFAULT_CONTAINERD_DEVICE = "/dev/disk/by-id/virtio-vantage-containerd"
DEFAULT_CONTAINERD_DISK_SIZE_GIB = 100

# Binary download URLs
VANTAGE_PROVIDER_BINARY_URL = "https://vantage-artifacts.vantagecompute.ai/binaries/vantage-provider/linux-amd64/latest/vantage-provider"
VANTAGE_NODE_SECURITY_BINARY_URL = "https://vantage-artifacts.vantagecompute.ai/binaries/vantage-node-security/linux-amd64/latest/vantage-node-security"

# Keycloak token endpoint path
KEYCLOAK_TOKEN_PATH = "/realms/vantage/protocol/openid-connect/token"
