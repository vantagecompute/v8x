# Copyright (C) 2025 Vantage Compute Corporation
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""Create service preset command."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.service_preset import PRESET_KINDS, service_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

# Kinds whose options are built from the shared sizing flags alone
# (everything kind-specific beyond sizing needs --body).
_SIZING_ONLY_KINDS = {"sweep", "tensorboard", "pipeline", "model", "trainjob", "inference"}


def _parse_body_json(body_json: str, name: str) -> dict:
    """Parse a raw --body payload, defaulting the name from the argument."""
    try:
        preset = json.loads(body_json)
    except json.JSONDecodeError as exc:
        raise Abort(
            f"--body is not valid JSON: {exc}",
            subject="Invalid Preset Body",
        ) from exc
    preset.setdefault("name", name)
    return preset


def _build_user_service_options(
    *,
    workloads: Optional[list[str]],
    sizing: dict,
    image_version: Optional[str],
    resolution: Optional[str],
    slurm_cluster: Optional[str],
) -> dict:
    if not workloads:
        raise Abort(
            "Provide at least one --workload (or a raw --body payload).",
            subject="Missing Workload",
        )
    options: dict = {
        "service_types": [w.lower() for w in workloads],
        "sizing": sizing,
    }
    if image_version:
        options["image_version"] = image_version
    if resolution:
        options["resolution"] = resolution
    if slurm_cluster:
        options["slurm_cluster"] = slurm_cluster
    return options


def _build_sizing_only_options(
    *,
    kind: str,
    sizing: dict,
    scratch_size: Optional[str],
    runtime: Optional[str],
) -> dict:
    options: dict = {"sizing": sizing}
    if kind == "model" and scratch_size:
        options["scratch_size"] = scratch_size
    if kind == "trainjob":
        if not runtime:
            raise Abort(
                "kind=trainjob requires --runtime (ClusterTrainingRuntime name).",
                subject="Missing Runtime",
            )
        options["runtime_ref"] = {"name": runtime}
    elif kind == "sweep" and runtime:
        options["runtime_ref"] = {"name": runtime}
    return options


def _build_preset_body(
    *,
    kind: str,
    name: str,
    workloads: Optional[list[str]],
    node_group: Optional[str],
    cpu: str,
    memory: str,
    gpu_count: int,
    scratch_size: Optional[str],
    runtime: Optional[str],
    image_version: Optional[str],
    resolution: Optional[str],
    slurm_cluster: Optional[str],
    description: Optional[str],
) -> dict:
    """Assemble an envelope+options preset body from the CLI flags."""
    kind = kind.lower()
    sizing: dict = {"cpu": cpu, "memory": memory}
    if gpu_count > 0:
        sizing["gpu"] = {"count": gpu_count}
    if node_group:
        sizing["node_group"] = node_group

    if kind == "user-service":
        options = _build_user_service_options(
            workloads=workloads,
            sizing=sizing,
            image_version=image_version,
            resolution=resolution,
            slurm_cluster=slurm_cluster,
        )
    elif kind in _SIZING_ONLY_KINDS:
        options = _build_sizing_only_options(
            kind=kind, sizing=sizing, scratch_size=scratch_size, runtime=runtime
        )
    else:
        raise Abort(
            f"kind '{kind}' cannot be built from flags — pass a raw --body payload.",
            subject="Unsupported Preset Kind",
        )

    preset = {
        "kind": kind,
        "name": name,
        "display_name": name,
        "options": options,
    }
    if description:
        preset["description"] = description
    return preset


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_service_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Preset name (RFC-1123 lowercase, e.g. 'shell-sm')"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    kind: Annotated[
        str,
        typer.Option(
            "--kind",
            "-k",
            help=f"Preset kind: {', '.join(sorted(PRESET_KINDS - {'session'}))}",
        ),
    ] = "user-service",
    workloads: Annotated[
        Optional[list[str]],
        typer.Option(
            "--workload",
            "-w",
            help="Workload(s) a user-service preset applies to "
            "(cloud-shell, remote-desktop, pvc-viewer; repeatable)",
        ),
    ] = None,
    node_group: Annotated[
        Optional[str],
        typer.Option("--node-group", "-n", help="Compute pool to schedule on (sizing.node_group)"),
    ] = None,
    cpu: Annotated[
        str,
        typer.Option("--cpu", help="CPU request (K8s quantity, e.g. '1')"),
    ] = "1",
    memory: Annotated[
        str,
        typer.Option("--memory", help="Memory request (K8s quantity, e.g. '2Gi')"),
    ] = "2Gi",
    gpu_count: Annotated[
        int,
        typer.Option("--gpu-count", help="GPU count (0 = CPU-only)"),
    ] = 0,
    scratch_size: Annotated[
        Optional[str],
        typer.Option(
            "--scratch-size",
            help="Scratch volume for artifact staging, e.g. '100Gi' (kind=model only)",
        ),
    ] = None,
    runtime: Annotated[
        Optional[str],
        typer.Option(
            "--runtime",
            help="ClusterTrainingRuntime name (required for kind=trainjob; "
            "optional default for kind=sweep)",
        ),
    ] = None,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            "--image-version", help="Default image tag for services created from this preset"
        ),
    ] = None,
    resolution: Annotated[
        Optional[str],
        typer.Option(
            "--resolution", "-r", help="Default desktop resolution (remote-desktop only)"
        ),
    ] = None,
    slurm_cluster: Annotated[
        Optional[str],
        typer.Option(
            "--slurm-cluster", help="Slurm cluster to attach (cloud-shell/remote-desktop)"
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Preset description"),
    ] = None,
    body_json: Annotated[
        Optional[str],
        typer.Option(
            "--body",
            help="Raw JSON preset body (any kind; overrides all other flags). "
            "Must carry the 'kind' discriminator.",
        ),
    ] = None,
):
    r"""Create a service preset on a Vantage cluster.

    Presets share a flat envelope (name, display_name, description, kind)
    plus a kind-specific 'options' object. Without --body this builds the
    options from the flags: kind=user-service uses --workload/--resolution/
    --slurm-cluster; sizing-only kinds (sweep, tensorboard, pipeline, model,
    trainjob, inference) use the shared sizing flags. Use --body for full
    control over any kind (session, sweep budgets, inference scale knobs, …).

    Examples:
        v8x cluster service-preset create shell-sm -c my-cluster \
            --workload cloud-shell --node-group shell-sm --cpu 1 --memory 2Gi

        v8x cluster service-preset create desktop-lg -c my-cluster \
            -w remote-desktop -n desktop-lg --cpu 4 --memory 8Gi -r 1920x1080

        v8x cluster service-preset create sweep-md -c my-cluster \
            --kind sweep --node-group sweep-md --cpu 2 --memory 8Gi

        v8x cluster service-preset create model-lg -c my-cluster \
            --kind model -n model-lg --cpu 4 --memory 16Gi --scratch-size 100Gi

        v8x cluster service-preset create vllm-7b -c my-cluster \
            --body '{"kind": "inference", "name": "vllm-7b", "options": {"flavor": "llm", ...}}'
    """
    console = ctx.obj.console

    if body_json:
        preset = _parse_body_json(body_json, name)
    else:
        preset = _build_preset_body(
            kind=kind,
            name=name,
            workloads=workloads,
            node_group=node_group,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            scratch_size=scratch_size,
            runtime=runtime,
            image_version=image_version,
            resolution=resolution,
            slurm_cluster=slurm_cluster,
            description=description,
        )

    try:
        console.print(
            f"[dim]Creating {preset.get('kind', '?')} preset [green]'{name}'[/green] "
            f"on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await service_preset_sdk.create(ctx, cluster_name=cluster_name, preset=preset)

        if response.status_code in (200, 201):
            data = response.json()
            console.print(
                f"[green]✓[/green] Preset [green]'{data.get('name', name)}'[/green] "
                f"(kind={data.get('kind', '?')}) created"
            )
        elif response.status_code == 409:
            console.print(f"[yellow]Preset '{name}' already exists[/yellow]")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to create preset: {error_detail}",
                subject="Preset Creation Failed",
                log_message=f"Preset creation failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create preset '{name}'.",
            details={"error": str(e)},
        )
