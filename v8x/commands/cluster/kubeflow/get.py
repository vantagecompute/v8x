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
"""Get Kubeflow status command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.application.kubeflow import kubeflow_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_kubeflow(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
):
    """Get the status of Kubeflow on a Vantage K8s cluster.

    Examples:
        v8x cluster kubeflow get --cluster my-cluster
    """
    console = ctx.obj.console

    try:
        response = await kubeflow_sdk.get(ctx, cluster_name=cluster_name)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            deployed = data.get("deployed", False)
            namespace = data.get("namespace", "")
            pod_count = data.get("pod_count", 0)
            components = data.get("components", {})

            if not deployed:
                console.print("[dim]Kubeflow is not deployed[/dim]")
                return

            # Status header
            status_color = (
                "green" if status == "running" else "yellow" if status == "deploying" else "red"
            )
            console.print(f"[bold]Kubeflow on '{cluster_name}'[/bold]")
            console.print(f"  Status:    [{status_color}]{status}[/{status_color}]")
            console.print(f"  Namespace: {namespace}")
            console.print(f"  Pods:      {pod_count}")

            # Component readiness
            if components:
                console.print("  Components:")
                for name, ready in components.items():
                    icon = "[green]\u2713[/green]" if ready else "[red]\u2717[/red]"
                    console.print(f"    {icon} {name}")
        else:
            console.print(
                f"[red]Error:[/red] vdeployer-web returned {response.status_code}: {response.text}"
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get Kubeflow status on '{cluster_name}'.",
            details={"error": str(e)},
        )
