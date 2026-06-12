# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Create secret command."""

import json
from typing import Any

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
async def create_secret(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Secret name (lowercase RFC-1123, max 40 chars)")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    secret_type: Annotated[
        str, typer.Option("--type", "-t", help="Secret type: huggingface or s3")
    ] = "huggingface",
    value: Annotated[
        str | None, typer.Option("--value", "-v", help="Secret value (HF token string)")
    ] = None,
    access_key_id: Annotated[
        str | None, typer.Option("--access-key-id", help="S3 access key ID")
    ] = None,
    secret_access_key: Annotated[
        str | None, typer.Option("--secret-access-key", help="S3 secret access key")
    ] = None,
    region: Annotated[
        str | None, typer.Option("--region", help="S3 region (e.g. us-east-1)")
    ] = None,
    endpoint_url: Annotated[
        str | None, typer.Option("--endpoint-url", help="S3 endpoint URL (non-AWS)")
    ] = None,
):
    r"""Create a secret (HuggingFace token or S3 credentials) in your profile namespace.

    Examples:
        v8x cluster secret create hf-token -c my-cluster --type huggingface --value hf_xxxxx
        v8x cluster secret create my-s3 -c my-cluster --type s3 \\
            --access-key-id AKIA... --secret-access-key xxx --region us-east-1
    """
    console = ctx.obj.console

    body: dict[str, Any] = {"name": name, "type": secret_type}

    if secret_type == "huggingface":
        if not value:
            raise Abort("--value required for huggingface secret", subject="Missing Input")
        body["value"] = value
    elif secret_type == "s3":
        if not access_key_id or not secret_access_key or not region:
            raise Abort(
                "--access-key-id, --secret-access-key, --region required for s3",
                subject="Missing Input",
            )
        s3_payload: dict[str, Any] = {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "region": region,
        }
        if endpoint_url:
            s3_payload["endpoint_url"] = endpoint_url
        body["value"] = s3_payload
    else:
        raise Abort(
            f"Unknown type: {secret_type}. Use huggingface or s3.", subject="Invalid Input"
        )

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/secrets"

        console.print(f"[dim]Creating {secret_type} secret '{name}'...[/dim]")

        async with get_http_client() as client:
            response = await client.post(url, json=body, headers=get_auth_headers(ctx))

        if response.status_code == 201:
            data = response.json()
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(f"[green]✓[/green] Secret '{name}' created ({secret_type})")
                console.print(f"  Namespace: {data.get('namespace', 'N/A')}")
        elif response.status_code == 409:
            console.print(f"[yellow]Secret '{name}' already exists[/yellow]")
        else:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            console.print(f"[red]Error:[/red] {response.status_code}: {detail}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to create secret.", details={"error": str(e)}
        )
