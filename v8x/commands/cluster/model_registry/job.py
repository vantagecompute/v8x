# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Get model onboarding job status."""

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
async def get_model_job(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID from model create")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
):
    """Check status of a model onboarding job.

    Examples:
        v8x cluster model-registry job <job-id> -c my-cluster
    """
    console = ctx.obj.console
    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        url = f"{get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)}/model/jobs/{job_id}"

        async with get_http_client() as client:
            response = await client.get(url, headers=get_auth_headers(ctx))

        if response.status_code != 200:
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json()
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        status = data.get("status", "UNKNOWN")
        color = {
            "COMPLETED": "green",
            "RUNNING": "blue",
            "PENDING": "yellow",
            "FAILED": "red",
        }.get(status, "white")
        console.print(f"  Status:   [{color}]{status}[/{color}]")
        if progress := data.get("progress"):
            console.print(f"  Progress: {progress}")
        if error := data.get("error"):
            console.print(f"  Error:    [red]{error}[/red]")
        if result := data.get("result"):
            console.print(f"  Artifact: {result.get('artifact', {}).get('artifact_uri', 'N/A')}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to get job.", details={"error": str(e)}
        )
