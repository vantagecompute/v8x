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
"""Create compute pool command."""

import json
from inspect import Parameter, signature
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.compute_pool import compute_pool_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_compute_pool(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name for the compute pool (DNS-safe, e.g. 'desktop-lg')"),
    ],
    cluster_name: str = typer.Option(
        ...,
        "--cluster",
        "-c",
        help="Name of the parent K8s cluster",
    ),
    instance_type: str = typer.Option(
        ...,
        "--instance-type",
        "-t",
        help="Instance type (e.g. 'sm', 'md', 'lg', 'slurm-control', 'slurm-compute-sm')",
    ),
    workload: Annotated[
        Optional[str],
        typer.Option(
            "--workload",
            "-w",
            help="Workload type for auto-populating taints/labels "
            "(slurm-admin, slurm-compute, kubeflow-workspace, kubeflow-train, "
            "kubeflow-inference, ray, mlflow, dynamo-frontend, dynamo-worker, "
            "remote-desktop, cloud-shell, pvc-viewer, general)",
        ),
    ] = None,
    min_size: Annotated[
        int,
        typer.Option("--min-size", help="Minimum number of nodes"),
    ] = 0,
    max_size: Annotated[
        int,
        typer.Option("--max-size", help="Maximum number of nodes"),
    ] = 10,
    gpu: Annotated[
        bool,
        typer.Option("--gpu/--no-gpu", help="Whether this compute pool has GPU resources"),
    ] = False,
    gpu_count: Annotated[
        int,
        typer.Option("--gpu-count", help="Number of GPUs per node (requires --gpu)"),
    ] = 0,
    control_plane: Annotated[
        bool,
        typer.Option(
            "--control-plane/--no-control-plane", help="Whether this is a control-plane pool"
        ),
    ] = False,
    root_disk_size: Annotated[
        Optional[int],
        typer.Option("--root-disk-size", help="Root disk size in GiB for autoscaled nodes"),
    ] = None,
    labels_json: Annotated[
        str,
        typer.Option(
            "--labels",
            help='Additional node labels as JSON (e.g. \'{"custom": "true"}\'). '
            "Standard labels are auto-populated from workload type.",
        ),
    ] = "{}",
    taint: Annotated[
        list[str] | None,
        typer.Option(
            "--taint",
            help="Additional taint as 'key=value:effect'. Standard taints are auto-populated from workload type.",
        ),
    ] = None,
):
    """Create a new compute pool within a Vantage K8s cluster.

    The --workload flag auto-populates taints, labels, and instance prefixes
    based on the workload type. You only need to provide name, instance-type,
    and sizing — the API handles the rest.

    Examples:
        v8x cluster compute-pool create desktop-lg -c my-cluster -t lg -w remote-desktop
        v8x cluster compute-pool create shell-sm -c my-cluster -t sm -w cloud-shell
        v8x cluster compute-pool create workspace-md -c my-cluster -t md -w kubeflow-workspace
        v8x cluster compute-pool create gpu-pool -c my-cluster -t lg -w kubeflow-inference --gpu --gpu-count 1
    """
    console = ctx.obj.console

    try:
        labels = json.loads(labels_json)
    except json.JSONDecodeError as e:
        raise Abort(
            f"Invalid JSON for --labels: {e}",
            subject="Invalid Input",
        ) from e

    taints = []
    if taint:
        for t in taint:
            if ":" not in t:
                raise Abort(
                    f"Invalid taint spec '{t}'. Use 'key=value:effect'.",
                    subject="Invalid Input",
                )
            kv, effect = t.rsplit(":", 1)
            if "=" in kv:
                key, value = kv.split("=", 1)
            else:
                key, value = kv, ""
            taints.append({"key": key, "value": value, "effect": effect})

    try:
        console.print(
            f"[dim]Creating compute pool [green]'{name}'[/green] on [green]'{cluster_name}'[/green]...[/dim]"
        )
        create_kwargs = {
            "cluster_name": cluster_name,
            "name": name,
            "instance_type": instance_type,
            "min_size": min_size,
            "max_size": max_size,
            "gpu": gpu,
            "gpu_count": gpu_count,
            "control_plane": control_plane,
            "labels": labels,
            "taints": taints,
            "workload": workload,
        }
        if root_disk_size is not None:
            sdk_parameters = signature(compute_pool_sdk.create).parameters
            supports_root_disk_size = "root_disk_size" in sdk_parameters or any(
                parameter.kind == Parameter.VAR_KEYWORD for parameter in sdk_parameters.values()
            )
            if not supports_root_disk_size:
                raise Abort(
                    "The installed vantage-sdkpy package does not support --root-disk-size yet. "
                    "Upgrade vantage-sdkpy before using this option.",
                    subject="SDK Upgrade Required",
                )
            create_kwargs["root_disk_size"] = root_disk_size

        response = await compute_pool_sdk.create(ctx, **create_kwargs)

        if response.status_code == 201:
            data = response.json() or {}
            console.print(f"[green]✓[/green] Compute pool [green]'{data['name']}'[/green] created")
            console.print(f"  Min size: {data['min_size']}, Max size: {data['max_size']}")
            if data.get("instance_type"):
                console.print(f"  Instance type: {data['instance_type']}")
        elif response.status_code == 409:
            result = response.json()
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'Compute pool already exists')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create compute pool '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
