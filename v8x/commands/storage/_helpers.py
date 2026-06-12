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
"""Shared helpers for storage commands."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import typer

if TYPE_CHECKING:
    from v8x.schemas import Persona

logger = logging.getLogger(__name__)


def get_username_from_persona(persona: Persona) -> str:
    """Return the Vantage username from the persona."""
    return persona.identity_data.username


def get_username_label(persona: Persona) -> dict[str, str]:
    """Return a labels dict with the vantage.io/username label."""
    return {"vantage.io/username": get_username_from_persona(persona)}


def get_namespace_from_persona(persona: Persona) -> str:
    """Derive a Kubernetes namespace from the persona email.

    The namespace is the email-based username with underscores replaced
    by hyphens so it satisfies the K8s naming rules.

    Example:
        user@example.com → user-examplecom
    """
    user, domain = persona.identity_data.email.split("@")
    username = f"{user}_{domain.replace('.', '')}"
    namespace = username.replace("_", "-")
    logger.debug("Derived namespace '%s' from email '%s'", namespace, persona.identity_data.email)
    return namespace


def resolve_namespace(persona: Persona, namespace: str | None) -> str:
    """Return *namespace* if explicitly provided, otherwise derive it from the persona."""
    if namespace:
        return namespace
    return get_namespace_from_persona(persona)


def get_vdeployer_web_url(cluster_name: str, org_id: str, vantage_url: str) -> str:
    """Construct the vdeployer-web base URL from cluster_name, org_id, and vantage_url."""
    import urllib.parse

    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    base_domain = hostname.removeprefix("app.")
    return f"https://{cluster_name}-{org_id}.clusters.{base_domain}/vdeployer"


def get_auth_headers(ctx: typer.Context) -> dict[str, str]:
    """Get authorization headers, refreshing the token if expired."""
    from v8x.deployment_apps.common import get_auth_headers as _get_auth_headers

    return _get_auth_headers(ctx)


def get_http_client(ctx: typer.Context, timeout: float = 30.0) -> httpx.AsyncClient:
    """Return an async HTTP client with authorization headers."""
    return httpx.AsyncClient(timeout=timeout, headers=get_auth_headers(ctx))
