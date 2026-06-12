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
"""Clouds alias command - maps to 'v8x cloud list'."""

import typer

from v8x.commands.cloud.list import list_command
from v8x.exceptions import handle_abort


@handle_abort
async def clouds_command(
    ctx: typer.Context,
) -> None:
    """List all available cloud providers.

    This is an alias for 'v8x cloud list'.

    Examples:
        $ v8x clouds
    """
    await list_command(ctx)
