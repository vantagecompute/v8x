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
"""List teams command."""

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
async def list_teams(ctx: typer.Context):
    """List all teams.

    Examples:
        v8x team list
        v8x team list --json
    """
    try:
        teams = await team_sdk.list_teams(ctx)

        if not teams:
            ctx.obj.formatter.render_list(
                data=[], resource_name="Teams", empty_message="No teams found."
            )
            return

        teams_data = []
        for team in teams:
            description = team.get("description")
            if description and len(description) > 50:
                description = description[:47] + "..."

            team_dict = {
                "id": team.get("id", ""),
                "name": team.get("name", ""),
                "description": description,
                "created_by": team.get("createdBy", ""),
                "sudo_enabled": bool(team.get("sudoEnabled", False)),
            }
            teams_data.append(team_dict)

        ctx.obj.formatter.render_list(
            data=teams_data,
            resource_name="Teams",
            empty_message="No teams found.",
            preferred_fields=["name", "id"],
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="An unexpected error occurred while listing teams.",
            details={"error": str(e)},
        )
