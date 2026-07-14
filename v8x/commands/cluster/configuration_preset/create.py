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
"""Create configuration preset command."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.configuration_preset import (
    CONFIGURATION_PRESET_KINDS,
    configuration_preset_sdk,
)

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


def _parse_body_json(body_json: str, name: str) -> dict:
    """Parse a raw --body payload, defaulting the name from the argument."""
    try:
        preset = json.loads(body_json)
    except json.JSONDecodeError as exc:
        raise Abort(
            f"--body is not valid JSON: {exc}",
            subject="Invalid Preset Body",
        ) from exc
    if not isinstance(preset, dict):
        raise Abort(
            "--body must be a JSON object (e.g. {...}).",
            subject="Invalid Preset Body",
        )
    preset.setdefault("name", name)
    return preset


def _build_user_service_options(
    *,
    workloads: Optional[list[str]],
    image_version: Optional[str],
    resolution: Optional[str],
    slurm_cluster: Optional[str],
) -> dict:
    if not workloads:
        raise Abort(
            "Provide at least one --workload (or a raw --body payload).",
            subject="Missing Workload",
        )
    options: dict = {"service_types": [w.lower() for w in workloads]}
    if image_version:
        options["image_version"] = image_version
    if resolution:
        options["resolution"] = resolution
    if slurm_cluster:
        options["slurm_cluster"] = slurm_cluster
    return options


def _build_options(
    *,
    kind: str,
    workloads: Optional[list[str]],
    image_version: Optional[str],
    resolution: Optional[str],
    slurm_cluster: Optional[str],
    runtime: Optional[str],
    nodes: int,
    proc_per_node: Optional[int],
    scratch_size: Optional[str],
    max_parallelism: Optional[int],
) -> dict:
    """Assemble kind-specific configuration options from the CLI flags."""
    if kind == "user-service":
        return _build_user_service_options(
            workloads=workloads,
            image_version=image_version,
            resolution=resolution,
            slurm_cluster=slurm_cluster,
        )
    if kind == "trainjob":
        if not runtime:
            raise Abort(
                "kind=trainjob requires --runtime (ClusterTrainingRuntime name).",
                subject="Missing Runtime",
            )
        options: dict = {"runtime_ref": {"name": runtime}, "nodes": nodes}
        if proc_per_node:
            options["proc_per_node"] = proc_per_node
        return options
    if kind == "sweep":
        options = {"nodes": nodes}
        if runtime:
            options["runtime_ref"] = {"name": runtime}
        if proc_per_node:
            options["proc_per_node"] = proc_per_node
        return options
    if kind == "model":
        return {"scratch_size": scratch_size} if scratch_size else {}
    if kind == "pipeline":
        return {"max_parallelism": max_parallelism} if max_parallelism else {}
    if kind in ("tensorboard", "inference"):
        # tensorboard has no options; inference scale/flavor knobs need --body.
        return {}
    raise Abort(
        f"kind '{kind}' cannot be built from flags — pass a raw --body payload.",
        subject="Unsupported Preset Kind",
    )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_configuration_preset(
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
            help=f"Preset kind: {', '.join(sorted(CONFIGURATION_PRESET_KINDS - {'session'}))}",
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
    runtime: Annotated[
        Optional[str],
        typer.Option(
            "--runtime",
            help="ClusterTrainingRuntime name (required for kind=trainjob; "
            "optional default for kind=sweep)",
        ),
    ] = None,
    nodes: Annotated[
        int,
        typer.Option("--nodes", help="Node count (kind=trainjob) / nodes per trial (kind=sweep)"),
    ] = 1,
    proc_per_node: Annotated[
        Optional[int],
        typer.Option("--proc-per-node", help="Processes per node (trainjob/sweep)"),
    ] = None,
    scratch_size: Annotated[
        Optional[str],
        typer.Option(
            "--scratch-size",
            help="Scratch volume for artifact staging, e.g. '100Gi' (kind=model only)",
        ),
    ] = None,
    max_parallelism: Annotated[
        Optional[int],
        typer.Option(
            "--max-parallelism", help="Concurrent pipeline task cap (kind=pipeline only)"
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
    r"""Create a configuration preset on a Vantage cluster.

    Configuration presets carry everything that is NOT sizing needed for
    vdeployer to assemble each kind's CRs — a flat envelope (name,
    description, kind) plus a kind-specific 'options' object. Pod shapes
    live in sizing presets ('v8x cluster sizing-preset'). Use --body for
    full control over any kind (session pod-size references, dynamo SLA,
    inference scale knobs, sweep budgets, …).

    Examples:
        v8x cluster configuration-preset create shell-sm -c my-cluster \
            --workload cloud-shell --slurm-cluster slurm1

        v8x cluster configuration-preset create desktop-lg -c my-cluster \
            -w remote-desktop -r 1920x1080 --image-version noble-3.3-0.2

        v8x cluster configuration-preset create train-torch -c my-cluster \
            --kind trainjob --runtime torch-distributed --nodes 2

        v8x cluster configuration-preset create model-lg -c my-cluster \
            --kind model --scratch-size 100Gi

        v8x cluster configuration-preset create vllm-7b -c my-cluster \
            --body '{"kind": "inference", "name": "vllm-7b", "options": {"flavor": "llm"}}'
    """
    console = ctx.obj.console

    if body_json:
        preset = _parse_body_json(body_json, name)
    else:
        kind = kind.lower()
        options = _build_options(
            kind=kind,
            workloads=workloads,
            image_version=image_version,
            resolution=resolution,
            slurm_cluster=slurm_cluster,
            runtime=runtime,
            nodes=nodes,
            proc_per_node=proc_per_node,
            scratch_size=scratch_size,
            max_parallelism=max_parallelism,
        )
        preset = {"kind": kind, "name": name, "options": options}
        if description:
            preset["description"] = description

    try:
        console.print(
            f"[dim]Creating {preset.get('kind', '?')} configuration preset "
            f"[green]'{name}'[/green] on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await configuration_preset_sdk.create(
            ctx, cluster_name=cluster_name, preset=preset
        )

        if response.status_code in (200, 201):
            data = response.json()
            console.print(
                f"[green]✓[/green] Configuration preset [green]'{data.get('name', name)}'[/green] "
                f"(kind={data.get('kind', '?')}) created"
            )
        elif response.status_code == 409:
            console.print(f"[yellow]Configuration preset '{name}' already exists[/yellow]")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to create configuration preset: {error_detail}",
                subject="Preset Creation Failed",
                log_message=f"Configuration preset creation failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create configuration preset '{name}'.",
            details={"error": str(e)},
        )
