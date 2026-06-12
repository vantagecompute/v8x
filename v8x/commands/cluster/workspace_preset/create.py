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
"""Create workspace preset command."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.workspace_preset import workspace_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_workspace_preset(
    ctx: typer.Context,
    display_name: Annotated[
        str,
        typer.Argument(
            help="Display name for the workspace preset (e.g. 'JupyterLab', 'Code Server')"
        ),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    description: Annotated[
        str,
        typer.Option(
            "--description",
            "-d",
            help="Description of the workspace preset",
        ),
    ] = "",
    ide_type: Annotated[
        str,
        typer.Option(
            "--ide-type",
            help="IDE type: JUPYTERLAB, CODESERVER, or RSTUDIO",
        ),
    ] = "JUPYTERLAB",
    pod_sizes_json: Annotated[
        Optional[str],
        typer.Option(
            "--pod-sizes",
            help="Pod sizes as JSON array. Each entry: "
            '\'[{"display_name":"sm","node_group":"workspace-sm","cpu":"1000m","memory":"2Gi"}]\'. '
            "Omit to auto-derive from kubeflow-workspace compute pools.",
        ),
    ] = None,
    home_pvc: Annotated[
        str,
        typer.Option(
            "--home-pvc",
            help="Name of the PVC for home directories",
        ),
    ] = "user-homes",
    hidden: Annotated[
        bool,
        typer.Option(
            "--hidden/--visible",
            help="Whether to hide this preset from the workspace creation UI",
        ),
    ] = False,
):
    r"""Create a workspace preset (WorkspaceKind) on a Vantage cluster.

    Workspace presets define IDE templates for Kubeflow workspaces. If --pod-sizes
    is omitted, the API auto-derives sizing options from all kubeflow-workspace
    compute pools.

    Examples:
        v8x cluster workspace-preset create "JupyterLab" -c my-cluster
        v8x cluster workspace-preset create "Code Server" -c my-cluster --ide-type CODESERVER
        v8x cluster workspace-preset create "JupyterLab GPU" -c my-cluster \\
            --pod-sizes '[{"display_name":"gpu-sm","node_group":"workspace-gpu","cpu":"4000m","memory":"16Gi","gpu_count":1}]'
    """
    console = ctx.obj.console

    pod_sizes = None
    if pod_sizes_json:
        try:
            pod_sizes = json.loads(pod_sizes_json)
        except json.JSONDecodeError as e:
            raise Abort(
                f"Invalid JSON for --pod-sizes: {e}",
                subject="Invalid Input",
            ) from e

    try:
        console.print(
            f"[dim]Creating workspace preset [green]'{display_name}'[/green] "
            f"on [green]'{cluster_name}'[/green]...[/dim]"
        )

        response = await workspace_preset_sdk.create(
            ctx,
            cluster_name=cluster_name,
            display_name=display_name,
            description=description,
            ide_type=ide_type,
            pod_sizes=pod_sizes,
            home_pvc=home_pvc,
            hidden=hidden,
        )

        if response.status_code in (200, 201):
            data = response.json()
            name = data.get("metadata", {}).get("name", data.get("name", "unknown"))
            console.print(f"[green]✓[/green] Workspace preset [green]'{name}'[/green] created")
            console.print(f"  Display name: {display_name}")
            console.print(f"  IDE type: {ide_type}")
            if pod_sizes is None:
                console.print("  Pod sizes: [dim]auto-derived from kubeflow-workspace pools[/dim]")
        elif response.status_code == 409:
            result = response.json()
            console.print(
                f"[yellow]Warning:[/yellow] {result.get('detail', 'Workspace preset already exists')}"
            )
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to create workspace preset '{display_name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
