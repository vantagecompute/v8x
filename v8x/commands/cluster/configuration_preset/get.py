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
"""Get configuration preset command."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.configuration_preset import (
    CONFIGURATION_PRESET_KINDS,
    configuration_preset_sdk,
)

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_configuration_preset(
    ctx: typer.Context,
    kind: Annotated[
        str,
        typer.Argument(help=f"Preset kind: {', '.join(sorted(CONFIGURATION_PRESET_KINDS))}"),
    ],
    name: Annotated[
        str,
        typer.Argument(help="Preset name"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
):
    """Get a single configuration preset by kind and name.

    Examples:
        v8x cluster configuration-preset get cloud-shell shell-sm -c my-cluster
        v8x cluster configuration-preset get dynamo prod-sla -c my-cluster
    """
    console = ctx.obj.console

    try:
        console.print(f"[dim]Fetching {kind} configuration preset '{name}'...[/dim]")

        response = await configuration_preset_sdk.get(
            ctx, cluster_name=cluster_name, kind=kind, name=name
        )

        if response.status_code == 200:
            console.print_json(json.dumps(response.json()))
        elif response.status_code == 404:
            raise Abort(
                f"Configuration preset not found: {kind}/{name}",
                subject="Preset Not Found",
                log_message=f"Configuration preset not found: {kind}/{name}",
            )
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to get configuration preset: {error_detail}",
                subject="Preset Get Failed",
                log_message=f"Configuration preset get failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get {kind} configuration preset '{name}'.",
            details={"error": str(e)},
        )
