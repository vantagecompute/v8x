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
"""Create inference preset command."""

from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.inference_preset import inference_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_inference_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Name for the preset (RFC-1123 lowercase, e.g. 'cpu-small')"),
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
            help="Compute pool name to schedule inference pods",
        ),
    ],
    runtimes: Annotated[
        list[str],
        typer.Option(
            "--runtime",
            "-r",
            help="Runtime name(s) this preset applies to (repeatable)",
        ),
    ],
    cpu: Annotated[
        str,
        typer.Option("--cpu", help="CPU request (K8s quantity, e.g. '2')"),
    ] = "2",
    memory: Annotated[
        str,
        typer.Option("--memory", help="Memory request (K8s quantity, e.g. '8Gi')"),
    ] = "8Gi",
    gpu_count: Annotated[
        int,
        typer.Option("--gpu-count", help="Number of GPUs (0 = CPU-only)"),
    ] = 0,
    min_replicas: Annotated[
        int,
        typer.Option("--min-replicas", help="Minimum replicas"),
    ] = 1,
    max_replicas: Annotated[
        int,
        typer.Option("--max-replicas", help="Maximum replicas"),
    ] = 1,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Preset description"),
    ] = None,
):
    r"""Create an inference preset on a Vantage cluster.

    Presets are reusable sizing templates that pre-fill the inference creation
    form. They are advisory — callers merge values into their own request body.

    Examples:
        v8x cluster preset create cpu-small -c my-cluster -p inference-cpu --runtime kserve-sklearn
        v8x cluster preset create gpu-vllm -c my-cluster -p inference-gpu --runtime vllm \\
            --cpu 4 --memory 16Gi --gpu-count 1 --max-replicas 3
    """
    console = ctx.obj.console

    try:
        console.print(
            f"[dim]Creating inference preset [green]'{name}'[/green] "
            f"on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await inference_preset_sdk.create(
            ctx,
            cluster_name=cluster_name,
            name=name,
            compute_pool=compute_pool,
            runtimes=runtimes,
            cpu=cpu,
            memory=memory,
            gpu_count=gpu_count,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            description=description,
        )

        if response.status_code in (200, 201):
            data = response.json()
            console.print(
                f"[green]✓[/green] Inference preset [green]'{data.get('name', name)}'[/green] created"
            )
            console.print(f"  CPU: {cpu}, Memory: {memory}, GPUs: {gpu_count}")
            console.print(f"  Compute pool: {compute_pool}")
            console.print(f"  Runtimes: {', '.join(runtimes)}")
        elif response.status_code == 409:
            result = response.json()
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'Preset already exists')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create inference preset '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
