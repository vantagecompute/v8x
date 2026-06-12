# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Test secret connectivity command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import (
    get_auth_headers,
    get_cluster_with_creds,
    get_http_client,
    get_vdeployer_web_url,
)


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def test_secret(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name to test")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Test S3 secret connectivity (ListBuckets dry-run).

    Examples:
        v8x cluster secret test my-s3 -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/secrets/{name}/test"

        async with get_http_client() as client:
            response = await client.post(url, headers=get_auth_headers(ctx))

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        if data.get("ok"):
            console.print(
                f"[green]✓[/green] Connection OK — {data.get('bucket_count', '?')} buckets accessible"
            )
        else:
            console.print(
                f"[red]✗[/red] Connection failed: {data.get('error_code', '')}: {data.get('error_message', '')}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to test secret.", details={"error": str(e)}
        )
