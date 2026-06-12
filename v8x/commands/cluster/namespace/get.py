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
"""Get namespace command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.namespace import namespace_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_namespace(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Namespace name")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
):
    """Get details of a specific namespace.

    Examples:
        v8x cluster namespace get vantage-kubeflow-james -c my-cluster
        v8x cluster namespace get vantage-kubeflow-james -c my-cluster --json
    """
    console = ctx.obj.console

    try:
        response = await namespace_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            if ctx.obj.json_output:
                print(json.dumps({"name": name, "exists": False}))
            else:
                console.print(f"[yellow]Namespace '{name}' not found on '{cluster_name}'[/yellow]")
            return

        if response.status_code != 200:
            raise Abort(f"Failed to get namespace: {response.text}", subject="API Error")

        data = response.json() or {}

        if ctx.obj.json_output:
            if isinstance(data, dict) and "exists" not in data:
                data["exists"] = True
            print(json.dumps(data, default=str))
            return

        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Name", data.get("name", name))
        table.add_row("Status", data.get("status", data.get("phase", "")))
        if labels := data.get("labels", {}):
            for k, v in labels.items():
                table.add_row(f"Label: {k}", v)

        console.print(Panel(table, title=f"Namespace: {name}"))

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get namespace '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
