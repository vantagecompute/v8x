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
"""Create team command."""

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
async def create_team(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the team")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Team description")
    ] = None,
    sudo_enabled: Annotated[
        bool, typer.Option("--sudo/--no-sudo", help="Enable sudo for team members")
    ] = False,
    roles: Annotated[
        list[str] | None,
        typer.Option("--role", "-r", help="Roles to assign (repeatable). Default: kubeflow-admin"),
    ] = None,
):
    """Create a new team.

    Automatically adds the creator as a member and assigns kubeflow-admin
    role (unless --role overrides).

    Examples:
        v8x team create my-team
        v8x team create ml-engineers -d "ML engineering team" --sudo
        v8x team create dev-team --role kubeflow-editor --role grafana-viewer
    """
    console = ctx.obj.console

    try:
        result = await team_sdk.create_team(ctx, name, description, sudo_enabled)
        team_id = result.get("id")

        if team_id:
            # Auto-add creator as member
            if ctx.obj.persona and ctx.obj.persona.identity_data:
                from jose import jwt as jose_jwt

                try:
                    claims = jose_jwt.get_unverified_claims(ctx.obj.persona.token_set.access_token)
                    user_id = claims.get("sub")
                    if user_id:
                        await team_sdk.add_user(ctx, team_id, user_id)
                        result["creator_added"] = True
                except Exception:
                    pass

            # Assign roles (default: kubeflow-admin)
            assign_roles = roles if roles else ["kubeflow-admin"]
            try:
                role_result = await team_sdk.update_roles(ctx, team_id, assign_roles)
                result["roles"] = role_result.get("roles", assign_roles)
            except Exception:
                pass

        ctx.obj.formatter.render_create(
            data=result,
            resource_name="Team",
            success_message=f"Team '{name}' created (id: {team_id or 'unknown'})",
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
