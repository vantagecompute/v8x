# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Onboard a model to the registry."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.model_registry import model_registry_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_model(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Model name")],
    version: Annotated[str, typer.Argument(help="Model version")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    source_type: Annotated[
        str, typer.Option("--source-type", "-s", help="Source type: huggingface, s3, url, local")
    ] = "huggingface",
    repo_id: Annotated[
        str | None, typer.Option("--repo-id", help="HuggingFace repo ID (e.g. google/gemma-4b-it)")
    ] = None,
    storage_uri: Annotated[
        str | None, typer.Option("--storage-uri", help="S3 URI for s3 source")
    ] = None,
    source_url: Annotated[str | None, typer.Option("--url", help="URL for url source")] = None,
    revision: Annotated[str, typer.Option("--revision", help="HF revision/branch")] = "main",
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Model description")
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite/--no-overwrite", help="Replace existing version")
    ] = False,
    sync: Annotated[bool, typer.Option("--sync/--async", help="Wait for completion")] = False,
    token_secret_name: Annotated[
        str | None,
        typer.Option("--token-secret", help="K8s Secret name with HF token (for gated models)"),
    ] = None,
):
    """Onboard a model to the registry.

    Examples:
        v8x cluster model-registry create gemma-4b v1 -c my-cluster --repo-id google/gemma-4b-it
        v8x cluster model-registry create my-model v1 -c my-cluster -s s3 --storage-uri s3://bucket/model/
    """
    console = ctx.obj.console

    try:
        console.print(f"[dim]Onboarding model '{name}' v{version}...[/dim]")
        response = await model_registry_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            version=version,
            source_type=source_type,
            repo_id=repo_id,
            storage_uri=storage_uri,
            source_url=source_url,
            revision=revision,
            description=description,
            overwrite=overwrite,
            sync=sync,
            token_secret_name=token_secret_name,
        )

        if response.status_code == 200:
            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print("[green]✓[/green] Model onboarding started")
                console.print(f"  Job ID: {data.get('job_id', 'N/A')}")
                console.print(f"  Status: {data.get('status', 'N/A')}")
                if result := data.get("result"):
                    console.print(
                        f"  Artifact: {result.get('artifact', {}).get('artifact_uri', 'N/A')}"
                    )
        else:
            data = response.json() or {}
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
            console.print(f"[red]Error:[/red] {response.status_code}: {detail}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to onboard model.", details={"error": str(e)}
        )
