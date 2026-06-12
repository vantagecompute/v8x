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

"""Templates for Vantage System on LXD app."""

from textwrap import dedent
from typing import Optional

from vantage_sdk.cluster.schema import VantageClusterContext

from .constants import KEYCLOAK_TOKEN_PATH, VANTAGE_PROVIDER_BINARY_URL


def download_vantage_lxd_script(
    vantage_cluster_ctx: VantageClusterContext,
    binary_path: str = "/usr/local/bin/vantage-lxd",
) -> str:
    """Generate script to download vantage-lxd binary with Keycloak authentication.

    Args:
        vantage_cluster_ctx: Context containing cluster credentials
        binary_path: Path where the binary should be installed

    Returns:
        Shell script string for downloading the binary
    """
    keycloak_token_url = f"{vantage_cluster_ctx.oidc_base_url}{KEYCLOAK_TOKEN_PATH}"

    return dedent(f"""\
        #!/bin/bash
        set -euo pipefail

        VANTAGE_PROVIDER_BINARY_URL="{VANTAGE_PROVIDER_BINARY_URL}"
        VANTAGE_KEYCLOAK_TOKEN_URL="{keycloak_token_url}"
        CLUSTER_CLIENT_ID="{vantage_cluster_ctx.client_id}"
        CLUSTER_CLIENT_SECRET="{vantage_cluster_ctx.client_secret}"
        BINARY_PATH="{binary_path}"

        # If Keycloak URL is configured, get a JWT token for authenticated download
        AUTH_HEADER=""
        if [ -n "$VANTAGE_KEYCLOAK_TOKEN_URL" ] && [ -n "$CLUSTER_CLIENT_ID" ] && [ -n "$CLUSTER_CLIENT_SECRET" ]; then
          echo "Getting JWT token from Keycloak for authenticated download..."
          TOKEN=$(curl -fsSL -X POST "$VANTAGE_KEYCLOAK_TOKEN_URL" \\
            -H "Content-Type: application/x-www-form-urlencoded" \\
            -d "grant_type=client_credentials" \\
            -d "client_id=$CLUSTER_CLIENT_ID" \\
            -d "client_secret=$CLUSTER_CLIENT_SECRET" | \\
            jq -r '.access_token') || {{
              echo "FATAL: Failed to get JWT token from Keycloak"
              exit 1
            }}
          AUTH_HEADER="Authorization: Bearer $TOKEN"
          echo "Got JWT token, downloading authenticated binary..."
        else
          echo "No Keycloak URL configured, downloading without authentication..."
        fi

        # Download the binary (with or without auth header)
        if [ -n "$AUTH_HEADER" ]; then
          curl -fsSL -H "$AUTH_HEADER" -o "$BINARY_PATH" "$VANTAGE_PROVIDER_BINARY_URL" || {{
            echo "FATAL: Failed to download vantage-provider binary (authenticated)"
            exit 1
          }}
        else
          curl -fsSL -o "$BINARY_PATH" "$VANTAGE_PROVIDER_BINARY_URL" || {{
            echo "FATAL: Failed to download vantage-provider binary"
            exit 1
          }}
        fi

        chmod +x "$BINARY_PATH"
        echo "vantage-provider binary installed to $BINARY_PATH"
        """)


def vantage_lxd_provision_command(
    vantage_cluster_ctx: VantageClusterContext,
    local_registry: Optional[str] = None,
    dev_mode: bool = False,
    binary_path: str = "/usr/local/bin/vantage-lxd",
) -> str:
    """Generate the vantage-lxd provision command.

    Args:
        vantage_cluster_ctx: Context containing cluster credentials and URLs
        local_registry: Optional local registry address (e.g., "192.168.1.100:5000")
        dev_mode: Whether to include --dev flag
        binary_path: Path to the vantage-lxd binary

    Returns:
        Shell command string for running vantage-lxd provision
    """
    # Build the vantage URL from oidc_base_url (auth.X.vantagecompute.ai -> app.X.vantagecompute.ai)
    vantage_url = vantage_cluster_ctx.oidc_base_url.replace("auth.", "app.")

    cmd_parts = [
        binary_path,
        "provision",
        f'--cluster-client-id "{vantage_cluster_ctx.client_id}"',
        f'--cluster-client-secret "{vantage_cluster_ctx.client_secret}"',
        f'--vantage-url "{vantage_url}"',
    ]

    if local_registry:
        cmd_parts.append(f'--local-registry "{local_registry}"')

    if dev_mode:
        cmd_parts.append("--dev")

    return " \\\n    ".join(cmd_parts)


def vantage_system_deploy_script(
    vantage_cluster_ctx: VantageClusterContext,
    local_registry: Optional[str] = None,
    dev_mode: bool = False,
) -> str:
    """Generate complete deployment script for Vantage System on LXD.

    This script:
    1. Downloads the vantage-lxd binary with Keycloak authentication
    2. Runs vantage-lxd provision to deploy vantage-system

    Args:
        vantage_cluster_ctx: Context containing cluster credentials and URLs
        local_registry: Optional local registry address
        dev_mode: Whether to include --dev flag

    Returns:
        Complete shell script for deployment
    """
    download_script = download_vantage_lxd_script(vantage_cluster_ctx)
    provision_cmd = vantage_lxd_provision_command(
        vantage_cluster_ctx=vantage_cluster_ctx,
        local_registry=local_registry,
        dev_mode=dev_mode,
    )

    return dedent(f"""\
        #!/bin/bash
        set -euo pipefail

        echo "=== Vantage System on LXD Deployment ==="
        echo ""

        # Step 1: Download vantage-lxd binary
        echo "Step 1: Downloading vantage-lxd binary..."
        {download_script}

        # Step 2: Run vantage-lxd provision
        echo ""
        echo "Step 2: Running vantage-lxd provision..."
        {provision_cmd}

        echo ""
        echo "=== Vantage System deployment complete! ==="
        """)
