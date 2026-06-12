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

"""List cluster networks command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.network import network_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

from ._helpers import network_items, print_network_table


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_networks(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
):
    """List Multus networks on a Vantage cluster.

    Examples:
        v8x cluster network list -c my-cluster
        v8x cluster network list -c my-cluster --json
    """
    console = ctx.obj.console

    try:
        response = await network_sdk.list(ctx, cluster_name=cluster_name)

        if response.status_code != 200:
            raise Abort(f"Failed to list networks: {response.text}", subject="API Error")

        networks = network_items(response.json())
        if ctx.obj.json_output:
            print(json.dumps(networks, default=str))
            return

        if not networks:
            console.print(f"No networks found on '{cluster_name}'")
            return

        print_network_table(console, networks, cluster_name=cluster_name)

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to list networks on '{cluster_name}'.",
            details={"error": str(e)},
        )
