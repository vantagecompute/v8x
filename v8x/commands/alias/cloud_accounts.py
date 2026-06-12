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
"""Cloud accounts alias command - maps to 'v8x cloud account list'."""

import typer

from v8x.commands.cloud.account.list import list_command
from v8x.exceptions import handle_abort


@handle_abort
async def cloud_accounts_command(
    ctx: typer.Context,
) -> None:
    """List all cloud accounts.

    This is an alias for 'v8x cloud account list'.

    Examples:
        $ v8x cloud-accounts
    """
    await list_command(ctx, provider=None)
