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
"""Create sizing preset command."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.sizing_preset import SIZING_PRESET_KINDS, sizing_preset_sdk

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
    kind: str,
    name: str,
    compute_pool: Optional[str],
    cpu: str,
    memory: str,
    gpu_count: int,
    description: Optional[str],
) -> dict:
    """Assemble an envelope+sizing preset body from the CLI flags."""
    sizing: dict = {"cpu": cpu, "memory": memory}
    if gpu_count > 0:
        sizing["gpu"] = {"count": gpu_count}
    if compute_pool:
        sizing["compute_pool"] = compute_pool

    preset = {
        "kind": kind.lower(),
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
async def create_sizing_preset(
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
            help=f"Preset kind: {', '.join(sorted(SIZING_PRESET_KINDS))}",
        ),
    ] = "user-service",
    compute_pool: Annotated[
        Optional[str],
        typer.Option(
            "--compute-pool", "-p", help="Compute pool to schedule on (sizing.compute_pool)"
        ),
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
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Preset description"),
    ] = None,
    body_json: Annotated[
        Optional[str],
        typer.Option(
            "--body",
            help="Raw JSON preset body (overrides all other flags). Must carry the 'kind' field.",
        ),
    ] = None,
):
    r"""Create a sizing preset on a Vantage cluster.

    Sizing presets are uniform pod-shape templates — a flat envelope
    (name, description, kind) plus one sizing object
    (cpu/memory/gpu/compute_pool) — shared by every workload kind
    (dynamo excepted: it derives pod shapes from its profiler).
    Kind-specific behaviour lives in configuration presets
    ('v8x cluster configuration-preset').

    Examples:
        v8x cluster sizing-preset create shell-sm -c my-cluster \
            --compute-pool shell-sm --cpu 1 --memory 2Gi

        v8x cluster sizing-preset create gpu-md -c my-cluster \
            --kind inference -p gpu-md --cpu 4 --memory 16Gi --gpu-count 1

        v8x cluster sizing-preset create train-lg -c my-cluster \
            --kind trainjob -p train-lg --cpu 32 --memory 128Gi --gpu-count 4
    """
    console = ctx.obj.console

    if body_json:
        preset = _parse_body_json(body_json, name)
    else:
        preset = _build_preset_body(
            kind=kind,
            name=name,
            compute_pool=compute_pool,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            description=description,
        )

    try:
        console.print(
            f"[dim]Creating {preset.get('kind', '?')} sizing preset [green]'{name}'[/green] "
            f"on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await sizing_preset_sdk.create(ctx, cluster_name=cluster_name, preset=preset)

        if response.status_code in (200, 201):
            data = response.json()
            console.print(
                f"[green]✓[/green] Sizing preset [green]'{data.get('name', name)}'[/green] "
                f"(kind={data.get('kind', '?')}) created"
            )
        elif response.status_code == 409:
            console.print(f"[yellow]Sizing preset '{name}' already exists[/yellow]")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to create sizing preset: {error_detail}",
                subject="Preset Creation Failed",
                log_message=f"Sizing preset creation failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create sizing preset '{name}'.",
            details={"error": str(e)},
        )
