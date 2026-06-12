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
"""Cloud management commands package."""

from v8x import AsyncTyper

from .account import account_app
from .get import get_command
from .list import list_command

cloud_app = AsyncTyper(
    name="cloud",
    help="Manage cloud provider configurations and cloud accounts.",
    no_args_is_help=True,
)

# System cloud type commands (read-only, queries Vantage API)
cloud_app.command("get")(get_command)
cloud_app.command("list")(list_command)

# Cloud account subcommand group (CRUD via Vantage API)
cloud_app.add_typer(account_app)
