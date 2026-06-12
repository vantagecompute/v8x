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
"""Add member to team command."""

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
async def add_team_member(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team name or ID")],
    user_id: Annotated[str, typer.Argument(help="User ID to add (Keycloak sub claim)")],
):
    """Add a user to a team.

    The user-id is the Keycloak 'sub' claim from the JWT token.
    Use 'v8x whoami --json' to find your user ID.

    Examples:
        v8x team add-member my-team <user-id>
    """
    console = ctx.obj.console

    try:
        team_id = await team_sdk.resolve_team_id(ctx, team)
        msg = await team_sdk.add_user(ctx, team_id, user_id)
        console.print(f"[green]✓[/green] {msg}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
