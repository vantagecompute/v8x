# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Create Dynamo deployment."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.dynamo_deployment import dynamo_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_dynamo(  # noqa: C901
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Deployment name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    model: Annotated[
        str, typer.Option("--model", "-m", help="Hugging Face model ID (e.g. Qwen/Qwen3-0.6B)")
    ],
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help="Target namespace (default: your profile ns)"),
    ] = None,
    backend: Annotated[
        str, typer.Option("--backend", "-b", help="Engine backend: auto, vllm, sglang, trtllm")
    ] = "auto",
    search_strategy: Annotated[
        str,
        typer.Option(
            "--search-strategy",
            help="rapid (~30s modeled profiling) or thorough (real-GPU sweeps)",
        ),
    ] = "rapid",
    no_auto_apply: Annotated[
        bool,
        typer.Option(
            "--no-auto-apply",
            help="Profile only; do not deploy the recommended config automatically",
        ),
    ] = False,
    ttft: Annotated[
        float | None, typer.Option("--ttft", help="SLA time-to-first-token target (ms)")
    ] = None,
    itl: Annotated[
        float | None, typer.Option("--itl", help="SLA inter-token latency target (ms)")
    ] = None,
    isl: Annotated[
        int | None, typer.Option("--isl", help="Expected input sequence length (tokens)")
    ] = None,
    osl: Annotated[
        int | None, typer.Option("--osl", help="Expected output sequence length (tokens)")
    ] = None,
    request_rate: Annotated[
        float | None, typer.Option("--request-rate", help="Expected requests per second")
    ] = None,
    concurrency: Annotated[
        int | None, typer.Option("--concurrency", help="Expected concurrent requests")
    ] = None,
    configuration_preset: Annotated[
        str | None,
        typer.Option(
            "--configuration-preset",
            "-C",
            help="Dynamo configuration preset; explicit flags win over preset values",
        ),
    ] = None,
    compute_pool: Annotated[
        str | None,
        typer.Option(
            "--compute-pool",
            "-p",
            help="dynamo-worker (GPU) compute pool for the engine pods",
        ),
    ] = None,
    frontend_compute_pool: Annotated[
        str | None,
        typer.Option(
            "--frontend-compute-pool",
            help="dynamo-frontend (CPU) compute pool for frontend/router pods",
        ),
    ] = None,
    router_mode: Annotated[
        str | None,
        typer.Option("--router-mode", help="Routing mode: round-robin, kv, least-loaded, random"),
    ] = None,
    planner_json: Annotated[
        str | None,
        typer.Option("--planner-json", help="PlannerConfig JSON (SLA-driven autoscaling)"),
    ] = None,
    dgd_overrides_json: Annotated[
        str | None,
        typer.Option(
            "--dgd-overrides-json",
            help="Partial DynamoGraphDeployment JSON merged into the generated DGD",
        ),
    ] = None,
):
    r"""Create a Dynamo model deployment (deploy-by-intent).

    Examples:
        v8x cluster dynamo create my-qwen -c my-cluster -m Qwen/Qwen3-0.6B \\
            --compute-pool dynamo-gpu --frontend-compute-pool dynamo-cpu
    """
    console = ctx.obj.console

    def _parse_json_object(raw: str | None, flag: str) -> dict | None:
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Abort(f"{flag} is not valid JSON: {exc}", subject="Invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise Abort(f"{flag} must be a JSON object.", subject="Invalid JSON")
        return parsed

    planner = _parse_json_object(planner_json, "--planner-json")
    dgd_overrides = _parse_json_object(dgd_overrides_json, "--dgd-overrides-json")

    try:
        console.print(f"[dim]Creating Dynamo deployment '{name}'...[/dim]")
        response = await dynamo_deployment_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            model=model,
            namespace=namespace,
            backend=backend,
            search_strategy=search_strategy,
            auto_apply=not no_auto_apply,
            ttft=ttft,
            itl=itl,
            isl=isl,
            osl=osl,
            request_rate=request_rate,
            concurrency=concurrency,
            configuration_preset=configuration_preset,
            compute_pool=compute_pool,
            frontend_compute_pool=frontend_compute_pool,
            router_mode=router_mode,
            planner=planner,
            dgd_overrides=dgd_overrides,
        )

        if response.status_code in (200, 201):
            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(f"[green]✓[/green] Dynamo deployment '{name}' created")
                console.print(f"  Model:   {data.get('model', model)}")
                console.print(f"  Backend: {data.get('backend', backend)}")
                console.print(f"  Phase:   {data.get('phase', 'N/A')}")
                console.print(f"  URL:     {data.get('url', 'N/A')}")
        else:
            data = response.json() or {}
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
            console.print(f"[red]Error:[/red] {response.status_code}: {detail}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to create Dynamo deployment.", details={"error": str(e)}
        )
