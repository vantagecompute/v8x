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
"""Cloud account management commands package.

Cloud accounts are organization-level registrations of cloud provider credentials
stored in the Vantage API at /admin/management/cloud_accounts.
"""

from v8x import AsyncTyper

from .create import create_command
from .delete import delete_command
from .get import get_command
from .list import list_command

account_app = AsyncTyper(
    name="account",
    help="Manage cloud accounts (organization-level cloud provider registrations).",
    no_args_is_help=True,
)

# Register account commands
account_app.command("create")(create_command)
account_app.command("delete")(delete_command)
account_app.command("get")(get_command)
account_app.command("list")(list_command)

__all__ = ["account_app"]
