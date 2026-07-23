# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Submit Ray job."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.ray_job import ray_job_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_ray_job(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="RayJob name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    entrypoint: Annotated[
        str,
        typer.Option("--entrypoint", "-e", help="Ray job entrypoint (e.g. 'python train.py')"),
    ],
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help="Target namespace (default: your profile ns)"),
    ] = None,
    configuration_preset: Annotated[
        str | None,
        typer.Option(
            "--configuration-preset",
            "-C",
            help="ray configuration preset; overrides win over preset values",
        ),
    ] = None,
    size_preset: Annotated[
        str | None,
        typer.Option(
            "--size-preset",
            "-p",
            help="ray size preset for the worker pod shape (overrides the preset's bundle)",
        ),
    ] = None,
    overrides_json: Annotated[
        str | None,
        typer.Option(
            "--overrides-json",
            help=(
                "Options JSON merged over the preset (image, workers, runtime_env, env, "
                "model_endpoints, ...)"
            ),
        ),
    ] = None,
):
    r"""Submit a Ray job (KubeRay RayJob).

    Examples:
        v8x cluster ray create train-1 -c my-cluster -e "python train.py" \\
            -C ray-md --overrides-json '{"workers": 3}'
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

    overrides = _parse_json_object(overrides_json, "--overrides-json")

    try:
        console.print(f"[dim]Submitting Ray job '{name}'...[/dim]")
        response = await ray_job_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            entrypoint=entrypoint,
            namespace=namespace,
            configuration_preset=configuration_preset,
            size_preset=size_preset,
            overrides=overrides,
        )

        if response.status_code not in (200, 201):
            raise Abort(f"Failed: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            print(json.dumps(data, default=str))
            return

        console.print(f"[green]✓[/green] Ray job '{data.get('name', name)}' submitted")
        console.print(f"  Namespace:   {data.get('namespace', 'N/A')}")
        console.print(f"  Ray Cluster: {data.get('ray_cluster_name', 'N/A')}")
        console.print(f"  Workers:     {data.get('workers', 'N/A')}")
        console.print(f"  Status:      {data.get('status', 'N/A')}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to submit Ray job.", details={"error": str(e)}
        )
