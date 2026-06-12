# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Create inference endpoint."""

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
async def create_inference(  # noqa: C901
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Endpoint name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    kind: Annotated[
        str, typer.Option("--kind", "-k", help="Endpoint kind: predictive or llm")
    ] = "predictive",
    model_source_type: Annotated[
        str,
        typer.Option(
            "--source-type",
            "-s",
            help="Model source: s3, huggingface, pvc, model_registry, custom",
        ),
    ] = "model_registry",
    model_id: Annotated[
        str | None,
        typer.Option("--model-id", help="Model ID (for model_registry or huggingface source)"),
    ] = None,
    storage_uri: Annotated[
        str | None, typer.Option("--storage-uri", help="S3 URI (for s3 source)")
    ] = None,
    image: Annotated[
        str | None, typer.Option("--image", help="Container image (for custom source)")
    ] = None,
    runtime: Annotated[
        str | None, typer.Option("--runtime", "-r", help="ClusterServingRuntime name")
    ] = None,
    compute_pool: Annotated[
        str | None, typer.Option("--compute-pool", "-p", help="Compute pool name")
    ] = None,
    cpu: Annotated[str, typer.Option("--cpu", help="CPU request")] = "2",
    memory: Annotated[str, typer.Option("--memory", help="Memory request")] = "8Gi",
    gpu_count: Annotated[int, typer.Option("--gpu-count", help="GPU count")] = 0,
    min_replicas: Annotated[int, typer.Option("--min-replicas", help="Min replicas")] = 1,
    max_replicas: Annotated[int, typer.Option("--max-replicas", help="Max replicas")] = 1,
    tensor_parallel: Annotated[
        int, typer.Option("--tensor-parallel", help="Tensor parallelism (LLM only)")
    ] = 1,
    framework: Annotated[
        str | None,
        typer.Option("--framework", help="Model framework (sklearn, pytorch, huggingface, etc.)"),
    ] = None,
    protocol_version: Annotated[
        str | None, typer.Option("--protocol-version", help="KServe protocol: v1, v2, or openai")
    ] = None,
    credentials_secret: Annotated[
        str | None,
        typer.Option(
            "--credentials-secret",
            help="Secret name for model access (e.g. hf-token for gated HF models)",
        ),
    ] = None,
):
    r"""Create an inference endpoint (predictive or LLM).

    Examples:
        v8x cluster inference-endpoint create my-sklearn -c my-cluster \\
            --source-type model_registry --model-id my-model --runtime kserve-sklearnserver

        v8x cluster inference-endpoint create my-llm -c my-cluster --kind llm \\
            --source-type huggingface --model-id google/gemma-4b-it --runtime kserve-vllm \\
            --gpu-count 1 --tensor-parallel 1
    """
    console = ctx.obj.console

    model_source: dict[str, Any]
    if model_source_type == "model_registry":
        if not model_id:
            raise Abort("--model-id required for model_registry source", subject="Missing Input")
        model_source = {"type": "model_registry", "model_id": model_id}
    elif model_source_type == "huggingface":
        if not model_id:
            raise Abort("--model-id required for huggingface source", subject="Missing Input")
        model_source = {"type": "huggingface", "model_id": model_id}
    elif model_source_type == "s3":
        if not storage_uri:
            raise Abort("--storage-uri required for s3 source", subject="Missing Input")
        model_source = {"type": "s3", "storage_uri": storage_uri}
    elif model_source_type == "custom":
        if not image:
            raise Abort("--image required for custom source", subject="Missing Input")
        model_source = {"type": "custom", "container": {"image": image}}
    else:
        raise Abort(f"Unknown source type: {model_source_type}", subject="Invalid Input")

    sizing: dict[str, Any] = {
        "cpu": cpu,
        "memory": memory,
        "min_replicas": min_replicas,
        "max_replicas": max_replicas,
    }
    if gpu_count > 0:
        sizing["gpus"] = {"vendor": "nvidia.com/gpu", "num": gpu_count}

    body: dict[str, Any] = {
        "name": name,
        "model_source": model_source,
        "sizing": sizing,
    }
    if runtime:
        body["runtime"] = runtime
    if framework:
        body["framework"] = framework
    if protocol_version:
        body["protocol_version"] = protocol_version
    if compute_pool:
        body["compute_pool"] = compute_pool
    if credentials_secret:
        body["credentials_secret"] = credentials_secret

    if kind == "llm":
        body["parallelism"] = {"tensor": tensor_parallel, "pipeline": 1, "data": 1}

    try:
        cluster = await get_cluster_with_creds(ctx, cluster_name)
        base = get_vdeployer_web_url(cluster.client_id, ctx.obj.settings.vantage_url)
        url = f"{base}/inferences/llm" if kind == "llm" else f"{base}/inferences"

        console.print(f"[dim]Creating {kind} inference '{name}'...[/dim]")

        async with get_http_client() as client:
            response = await client.post(url, json=body, headers=get_auth_headers(ctx))

        if response.status_code in (200, 201):
            data = response.json()
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(f"[green]✓[/green] Inference endpoint '{name}' created")
                console.print(f"  Kind:   {data.get('kind', kind)}")
                console.print(f"  URL:    {data.get('url', 'N/A')}")
                console.print(f"  Status: {data.get('status', {}).get('phase', 'N/A')}")
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
            error_message="Failed to create inference.", details={"error": str(e)}
        )
