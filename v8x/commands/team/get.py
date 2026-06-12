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
"""Get team command."""

from typing import Annotated

import typer
from vantage_sdk.exceptions import Abort
from vantage_sdk.team.crud import team_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_team(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team name or ID to retrieve")],
):
    """Get details of a specific team.

    Returns the same core fields as `team create` so JSON output is consistent
    between creation and retrieval flows.
    """
    try:
        team_id = await team_sdk.resolve_team_id(ctx, team)
        team_data = await team_sdk.get_team(ctx, team_id)

        if not team_data:
            raise Abort(
                f"Team '{team}' not found.",
                subject="Team Not Found",
                log_message=f"Team not found: {team}",
            )

        normalized_team = {
            "id": team_data.get("id", ""),
            "name": team_data.get("name", ""),
            "description": team_data.get("description", ""),
            "createdAt": team_data.get("createdAt", ""),
            "createdBy": team_data.get("createdBy", ""),
            "organization": team_data.get("organization", ""),
            "sudoEnabled": bool(team_data.get("sudoEnabled", False)),
        }

        ctx.obj.formatter.render_get(
            data=normalized_team,
            resource_name="Team",
            resource_id=team_id,
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to get team '{team}'.",
            details={"error": str(e)},
        )
