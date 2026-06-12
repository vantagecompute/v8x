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

"""Get cluster network command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.network import network_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import print_network_detail


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_network(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name")],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
):
    """Get details for a Multus network.

    Examples:
        v8x cluster network get data-net -c my-cluster
        v8x cluster network get data-net -c my-cluster --json
    """
    console = ctx.obj.console

    try:
        response = await network_sdk.get(ctx, cluster_name=cluster_name, name=name)

        if response.status_code == 404:
            if ctx.obj.json_output:
                print(json.dumps({"name": name, "exists": False}))
            else:
                console.print(f"[yellow]Network '{name}' not found on '{cluster_name}'[/yellow]")
            return

        if response.status_code != 200:
            raise Abort(f"Failed to get network: {response.text}", subject="API Error")

        data = response.json() or {}
        if ctx.obj.json_output:
            if isinstance(data, dict) and "exists" not in data:
                data["exists"] = True
            print(json.dumps(data, default=str))
            return

        print_network_detail(console, data, title=f"Network: {name}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get network '{name}' on '{cluster_name}'.",
            details={"error": str(e)},
        )
