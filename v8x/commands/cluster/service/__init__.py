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
"""Service management commands for Vantage clusters."""

from v8x import AsyncTyper

from .create import create_user_service
from .delete import delete_user_service
from .disable import disable_service
from .enable import enable_service
from .get import get_user_service
from .list import list_user_services
from .update import update_service

# Create the service command group
service_app = AsyncTyper(
    name="service",
    help="Enable, disable, update, or manage user services on a Vantage cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

# Register subcommands for cluster-level services
service_app.command("enable")(enable_service)
service_app.command("disable")(disable_service)
service_app.command("update")(update_service)

# Register subcommands for user services (pvc-viewer, cloud-shell, remote-desktop)
service_app.command("create")(create_user_service)
service_app.command("delete")(delete_user_service)
service_app.command("get")(get_user_service)
service_app.command("list")(list_user_services)
