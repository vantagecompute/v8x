# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Delete cluster network command."""

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.network import network_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def delete_network(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name to delete")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Delete a Multus network from a Vantage cluster.

    Examples:
        v8x cluster network delete data-net -c my-cluster
        v8x cluster network delete data-net -c my-cluster --force
    """
    console = ctx.obj.console

    if not force:
        confirm = typer.confirm(f"Delete network '{name}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        response = await network_sdk.delete(ctx, cluster_name=cluster_name, name=name)

        if response.status_code in (200, 202, 204):
            console.print(f"[green]✓[/green] Network '{name}' deleted")
        elif response.status_code == 404:
            console.print(f"[yellow]Network '{name}' not found[/yellow]")
        else:
            raise Abort(f"Failed to delete network: {response.text}", subject="API Error")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete network '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
