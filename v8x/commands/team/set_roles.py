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
"""Set roles on a team."""

import typer
from typing_extensions import Annotated
from vantage_sdk.team.crud import team_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def set_team_roles(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team name or ID")],
    role: Annotated[
        list[str],
        typer.Option(
            "--role", "-r", help="Role name (repeatable). e.g. kubeflow-admin, kubeflow-editor"
        ),
    ],
):
    """Set roles on a team (replaces existing roles).

    Common roles: kubeflow-admin, kubeflow-editor, kubeflow-viewer,
    grafana-admin, grafana-editor, grafana-viewer, sudo.

    Examples:
        v8x team set-roles my-team --role kubeflow-admin
        v8x team set-roles my-team --role kubeflow-admin --role grafana-editor
    """
    console = ctx.obj.console

    try:
        team_id = await team_sdk.resolve_team_id(ctx, team)
        result = await team_sdk.update_roles(ctx, team_id, role)
        assigned = result.get("roles", role)
        console.print(f"[green]✓[/green] Roles set: {', '.join(assigned)}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
