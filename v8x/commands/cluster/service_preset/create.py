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
from vantage_sdk.workbench.service_preset import service_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


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
    image_version: Annotated[
        Optional[str],
        typer.Option("--image-version", help="Default image tag for services created from this preset"),
    ] = None,
    resolution: Annotated[
        Optional[str],
        typer.Option("--resolution", "-r", help="Default desktop resolution (remote-desktop only)"),
    ] = None,
    slurm_cluster: Annotated[
        Optional[str],
        typer.Option("--slurm-cluster", help="Slurm cluster to attach (cloud-shell/remote-desktop)"),
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

    Without --body this builds a kind=user-service preset from the flags.
    Use --body to create any other preset kind (inference, trainjob, session)
    from a raw JSON payload.

    Examples:
        v8x cluster service-preset create shell-sm -c my-cluster \\
            --workload cloud-shell --node-group shell-sm --cpu 1 --memory 2Gi

        v8x cluster service-preset create desktop-lg -c my-cluster \\
            -w remote-desktop -n desktop-lg --cpu 4 --memory 8Gi -r 1920x1080

        v8x cluster service-preset create vllm-7b -c my-cluster \\
            --body '{"kind": "inference", "name": "vllm-7b", "flavor": "llm", ...}'
    """
    console = ctx.obj.console

    if body_json:
        try:
            preset = json.loads(body_json)
        except json.JSONDecodeError as exc:
            raise Abort(
                f"--body is not valid JSON: {exc}",
                subject="Invalid Preset Body",
            ) from exc
        preset.setdefault("name", name)
    else:
        if not workloads:
            raise Abort(
                "Provide at least one --workload (or a raw --body payload).",
                subject="Missing Workload",
            )
        sizing: dict = {"cpu": cpu, "memory": memory}
        if node_group:
            sizing["node_group"] = node_group
        preset = {
            "kind": "user-service",
            "name": name,
            "display_name": name,
            "service_types": [w.lower() for w in workloads],
            "sizing": sizing,
        }
        if description:
            preset["description"] = description
        if image_version:
            preset["image_version"] = image_version
        if resolution:
            preset["resolution"] = resolution
        if slurm_cluster:
            preset["slurm_cluster"] = slurm_cluster

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
