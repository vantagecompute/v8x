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
"""Miscellaneous cluster command helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.exceptions import Abort

from v8x.config import Settings


def get_cloud_choices() -> list[str]:
    """Get the list of built-in supported cloud types from settings."""
    settings = Settings()
    return settings.supported_clouds


def get_app_choices() -> list[str]:
    """Get the list of available deployment apps."""
    try:
        # Import SDK here to avoid module-level initialization
        from v8x.deployment_apps import deployment_app_sdk

        apps = deployment_app_sdk.list()
        choices = [app.name for app in apps]
        return choices
    except Exception:
        return []


def get_vdeployer_web_url(client_id: str, vantage_url: str) -> str:
    """Construct the vdeployer-web base URL from client_id and vantage_url."""
    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    base_domain = hostname.removeprefix("app.")
    return f"https://{client_id}.clusters.{base_domain}/vdeployer"


def validate_cluster_credentials(cluster) -> None:
    """Ensure the cluster has the credentials required for vdeployer-web updates."""
    if not getattr(cluster, "client_secret", None):
        raise Abort(
            "Cluster is missing client secret. Cannot trigger vdeployer-web update.",
            subject="Missing Credentials",
            log_message="Cluster missing client_secret",
        )
    if not getattr(cluster, "sssd_binder_password", None):
        raise Abort(
            "Cluster is missing SSSD binder password. Cannot trigger vdeployer-web update.",
            subject="Missing Credentials",
            log_message="Cluster missing sssd_binder_password",
        )


async def resolve_provider(ctx, cluster) -> str:
    """Resolve the provider name from the cluster cloud account."""
    cloud_account_id = getattr(cluster, "cloud_account_id", None)
    if not cloud_account_id:
        return ""

    cloud_account = await cloud_account_sdk.get(ctx, int(cloud_account_id))
    if not cloud_account:
        return ""

    provider = cloud_account.provider.lower() if cloud_account.provider else ""
    cloud_attrs = cloud_account.attributes or {}
    if "vantage_cloud_type" in cloud_attrs:
        provider = cloud_attrs["vantage_cloud_type"]
    if provider == "microk8s":
        provider = "k8s"
    return provider


def build_vdeployer_settings(
    settings: dict[str, Any],
    provider: str,
    cluster,
    persona,
) -> dict[str, Any]:
    """Build the settings dict for a vdeployer-web deploy request."""
    org_id = getattr(getattr(persona, "identity_data", None), "org_id", None)
    if not org_id:
        raise Abort("Missing organization context.", subject="Authentication Required")

    vdeployer_settings = dict(settings)
    vdeployer_settings["provider"] = provider
    vdeployer_settings["cluster_name"] = cluster.name
    vdeployer_settings["keycloak_client_id"] = cluster.client_id
    vdeployer_settings["keycloak_client_secret"] = cluster.client_secret
    vdeployer_settings["keycloak_organization_id"] = org_id
    vdeployer_settings["sssd_binder_password"] = cluster.sssd_binder_password

    creation_params = getattr(cluster, "creation_parameters", {}) or {}
    if jupyterhub_token := creation_params.get("jupyterhub_token"):
        vdeployer_settings["jupyterhub_service_token"] = jupyterhub_token

    return vdeployer_settings


async def send_vdeployer_request(
    console,
    method: str,
    url: str,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Send a request to vdeployer-web and return the decoded JSON body when possible."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, json=json_data, headers=headers)

    if response.status_code >= 400:
        raise Abort(
            f"vdeployer-web returned {response.status_code}: {response.text}",
            subject="API Error",
            log_message=f"{method} {url} failed with {response.status_code}",
        )

    try:
        return response.json()
    except ValueError:
        if console:
            console.print("[dim]vdeployer-web returned an empty response body[/dim]")
        return None
