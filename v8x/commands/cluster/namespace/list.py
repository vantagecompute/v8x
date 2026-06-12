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
"""List namespaces command."""

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
async def list_namespaces(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
):
    """List namespaces on a Vantage cluster.

    Examples:
        v8x cluster namespace list -c my-cluster
        v8x cluster namespace list -c my-cluster --json
    """
    console = ctx.obj.console

    try:
        response = await namespace_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed to list namespaces: {response.text}", subject="API Error")

        data = response.json() or []
        namespaces = data if isinstance(data, list) else data.get("items", [])

        if ctx.obj.json_output:
            print(json.dumps(namespaces, default=str))
            return

        if not namespaces:
            console.print(f"No namespaces found on '{cluster_name}'")
            return

        from rich.table import Table

        table = Table(title=f"Namespaces on '{cluster_name}'")
        table.add_column("Name", style="bold")
        table.add_column("Status")

        for ns in namespaces:
            name = ns.get("name", ns.get("metadata", {}).get("name", ""))
            status = ns.get("status", ns.get("phase", ""))
            table.add_row(name, status or "[dim]-[/dim]")

        console.print(table)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list namespaces on '{cluster_name}'.",
            details={"error": str(e)},
        )
