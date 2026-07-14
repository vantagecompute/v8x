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
"""Delete configuration preset command."""

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
async def delete_configuration_preset(
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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """Delete a configuration preset (idempotent server-side).

    Examples:
        v8x cluster configuration-preset delete user-service shell-sm -c my-cluster --force
    """
    console = ctx.obj.console

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete {kind} configuration preset '{name}'?"
        )
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        console.print(f"[dim]Deleting {kind} configuration preset '{name}'...[/dim]")

        response = await configuration_preset_sdk.delete(
            ctx, cluster_name=cluster_name, kind=kind, name=name
        )

        if response.status_code in (200, 204):
            console.print(f"[green]✓[/green] Configuration preset '{name}' deleted")
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to delete configuration preset: {error_detail}",
                subject="Preset Delete Failed",
                log_message=f"Configuration preset delete failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to delete {kind} configuration preset '{name}'.",
            details={"error": str(e)},
        )
