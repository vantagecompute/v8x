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
"""Add resource to team command."""

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
async def add_team_resource(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team name or ID")],
    resource_id: Annotated[str, typer.Argument(help="Resource ID (e.g. cluster client_id)")],
    resource_type: Annotated[str, typer.Option("--type", "-t", help="Resource type")] = "CLUSTER",
):
    """Add a resource (e.g. cluster) to a team.

    This associates the resource with the team so the profile reconciler
    can create kubeflow profiles for team members on that cluster.

    Examples:
        v8x team add-resource my-team <cluster-client-id>
    """
    console = ctx.obj.console

    try:
        team_id = await team_sdk.resolve_team_id(ctx, team)
        msg = await team_sdk.add_resource(ctx, team_id, resource_id, resource_type)
        console.print(f"[green]✓[/green] {msg}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
