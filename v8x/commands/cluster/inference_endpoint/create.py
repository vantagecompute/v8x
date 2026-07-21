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


def _build_overrides(override: list[str] | None, overrides_json: str | None) -> dict | None:
    """Assemble the request 'overrides' object from --overrides-json + -o KEY=VALUE.

    JSON supplies the base (for nested options like parallelism/env); repeated
    -o entries layer simple top-level keys on top. Values are passed as
    strings — the server coerces typed fields.
    """
    out: dict = {}
    if overrides_json:
        try:
            parsed = json.loads(overrides_json)
        except json.JSONDecodeError as exc:
            raise Abort(
                f"--overrides-json is not valid JSON: {exc}",
                subject="Invalid Overrides",
            ) from exc
        if not isinstance(parsed, dict):
            raise Abort(
                "--overrides-json must be a JSON object (e.g. {...}).",
                subject="Invalid Overrides",
            )
        out.update(parsed)
    for entry in override or []:
        key, sep, value = entry.partition("=")
        if not sep or not key:
            raise Abort(
                f"--override entries must be KEY=VALUE (got '{entry}').",
                subject="Invalid Overrides",
            )
        out[key] = value
    return out or None


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
    size_preset: Annotated[
        str | None,
        typer.Option(
            "--size-preset",
            "-P",
            help="Inference size preset supplying cpu/memory/gpu + compute pool",
        ),
    ] = None,
    configuration_preset: Annotated[
        str | None,
        typer.Option(
            "--configuration-preset",
            "-C",
            help="Inference configuration preset supplying runtime/protocol/"
            "scaling/args/env; omit to use the cluster's default preset",
        ),
    ] = None,
    compute_pool: Annotated[
        str | None, typer.Option("--compute-pool", "-p", help="Compute pool name")
    ] = None,
    cpu: Annotated[
        str | None, typer.Option("--cpu", help="CPU override (unset: size preset)")
    ] = None,
    memory: Annotated[
        str | None, typer.Option("--memory", help="Memory override (unset: size preset)")
    ] = None,
    gpu_count: Annotated[
        int | None, typer.Option("--gpu-count", help="GPU count override (unset: size preset)")
    ] = None,
    framework: Annotated[
        str | None,
        typer.Option("--framework", help="Model framework (sklearn, pytorch, huggingface, etc.)"),
    ] = None,
    credentials_secret: Annotated[
        str | None,
        typer.Option(
            "--credentials-secret",
            help="Secret name for model access (e.g. hf-token for gated HF models)",
        ),
    ] = None,
    override: Annotated[
        list[str] | None,
        typer.Option(
            "--override",
            "-o",
            help="Configuration override KEY=VALUE (repeatable; top-level option "
            "keys, e.g. -o runtime=kserve-vllm -o max_replicas=3). Scalars "
            "replace the preset value; use --overrides-json for nested options",
        ),
    ] = None,
    overrides_json: Annotated[
        str | None,
        typer.Option(
            "--overrides-json",
            help='Raw JSON configuration overrides (same shape as the preset\'s '
            'options, e.g. \'{"parallelism": {"tensor": 2}, "env": {"K": "V"}}\'); '
            "env merges by name, args append, scalars replace",
        ),
    ] = None,
):
    r"""Create an inference endpoint (predictive or LLM).

    Non-sizing configuration (runtime, protocol, scaling knobs, args/env)
    comes from the configuration preset — or the cluster's default preset
    when none is named. Per-create deltas go through -o/--overrides-json.
    Preview the effective configuration with
    'v8x cluster configuration-preset resolve'.

    Examples:
        v8x cluster inference-endpoint create my-sklearn -c my-cluster \\
            --source-type model_registry --model-id my-model \\
            --configuration-preset cpu-medium

        v8x cluster inference-endpoint create my-llm -c my-cluster --kind llm \\
            --source-type huggingface --model-id google/gemma-4b-it \\
            --configuration-preset gpu-medium -o runtime=kserve-vllm \\
            --overrides-json '{"parallelism": {"tensor": 1}}'
    """
    console = ctx.obj.console
    overrides = _build_overrides(override, overrides_json)

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
            size_preset=size_preset,
            configuration_preset=configuration_preset,
            compute_pool=compute_pool,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            framework=framework,
            credentials_secret=credentials_secret,
            overrides=overrides,
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
