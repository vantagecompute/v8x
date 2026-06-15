# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Create inference endpoint."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.inference_endpoint import inference_endpoint_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


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

    try:
        console.print(f"[dim]Creating {kind} inference '{name}'...[/dim]")
        response = await inference_endpoint_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            kind=kind,
            model_source_type=model_source_type,
            model_id=model_id,
            storage_uri=storage_uri,
            image=image,
            runtime=runtime,
            compute_pool=compute_pool,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            tensor_parallel=tensor_parallel,
            framework=framework,
            protocol_version=protocol_version,
            credentials_secret=credentials_secret,
        )

        if response.status_code in (200, 201):
            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(f"[green]✓[/green] Inference endpoint '{name}' created")
                console.print(f"  Kind:   {data.get('kind', kind)}")
                console.print(f"  URL:    {data.get('url', 'N/A')}")
                console.print(f"  Status: {data.get('status', {}).get('phase', 'N/A')}")
        else:
            data = response.json() or {}
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
            console.print(f"[red]Error:[/red] {response.status_code}: {detail}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to create inference.", details={"error": str(e)}
        )
