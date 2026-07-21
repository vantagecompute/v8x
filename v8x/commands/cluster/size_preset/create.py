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
"""Create size preset command."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.size_preset import size_preset_sdk

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


def _build_preset_body(
    *,
    name: str,
    compute_pool: str,
    cpu: str,
    memory: str,
    gpu_count: int,
    description: Optional[str],
) -> dict:
    """Assemble an envelope+size preset body from the CLI flags."""
    sizing: dict = {"cpu": cpu, "memory": memory, "compute_pool": compute_pool}
    if gpu_count > 0:
        sizing["gpu"] = {"count": gpu_count}

    preset = {
        "name": name,
        "sizing": sizing,
    }
    if description:
        preset["description"] = description
    return preset


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_size_preset(
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
    compute_pool: Annotated[
        str,
        typer.Option(
            "--compute-pool",
            "-p",
            help="Compute pool to schedule on (required; determines the preset's workload)",
        ),
    ],
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
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Preset description"),
    ] = None,
    body_json: Annotated[
        Optional[str],
        typer.Option(
            "--body",
            help=(
                "Raw JSON preset body (overrides all other flags). "
                "Must carry 'sizing.compute_pool'."
            ),
        ),
    ] = None,
):
    r"""Create a size preset on a Vantage cluster.

    Size presets are uniform pod-shape templates — a flat envelope
    (name, description) plus one sizing object
    (cpu/memory/gpu/compute_pool). The preset's workload catalog is
    derived server-side from the compute pool's workload label — it is
    never sent in the request body. Workload-specific behaviour lives in
    configuration presets ('v8x cluster configuration-preset').

    Examples:
        v8x cluster size-preset create shell-sm -c my-cluster \
            --compute-pool shell-sm --cpu 1 --memory 2Gi

        v8x cluster size-preset create gpu-md -c my-cluster \
            -p gpu-md --cpu 4 --memory 16Gi --gpu-count 1

        v8x cluster size-preset create train-lg -c my-cluster \
            -p train-lg --cpu 32 --memory 128Gi --gpu-count 4
    """
    console = ctx.obj.console

    if body_json:
        preset = _parse_body_json(body_json, name)
    else:
        preset = _build_preset_body(
            name=name,
            compute_pool=compute_pool,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            description=description,
        )

    try:
        console.print(
            f"[dim]Creating size preset [green]'{name}'[/green] "
            f"on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await size_preset_sdk.create(ctx, cluster_name=cluster_name, preset=preset)

        if response.status_code in (200, 201):
            data = response.json()
            console.print(
                f"[green]✓[/green] Size preset [green]'{data.get('name', name)}'[/green] "
                f"(workload={data.get('workload', '?')}) created"
            )
        elif response.status_code == 409:
            console.print(f"[yellow]Size preset '{name}' already exists[/yellow]")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to create size preset: {error_detail}",
                subject="Preset Creation Failed",
                log_message=f"Size preset creation failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create size preset '{name}'.",
            details={"error": str(e)},
        )
