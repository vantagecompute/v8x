# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Shared helpers for inference-endpoint CLI commands."""

import urllib.parse

import httpx
import typer
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

VDEPLOYER_TIMEOUT = 60.0


def get_vdeployer_web_url(client_id: str, vantage_url: str) -> str:
    parsed = urllib.parse.urlparse(vantage_url)
    hostname = parsed.hostname or ""
    base_domain = hostname.removeprefix("app.")
    return f"https://{client_id}.clusters.{base_domain}/vdeployer"


async def get_cluster_with_creds(ctx: typer.Context, cluster_name: str):
    cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
    if not cluster:
        raise Abort(f"Cluster '{cluster_name}' not found.", subject="Cluster Not Found")
    return cluster


def get_auth_headers(ctx: typer.Context) -> dict[str, str]:
    return {"Authorization": f"Bearer {ctx.obj.persona.token_set.access_token}"}


def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=VDEPLOYER_TIMEOUT)
