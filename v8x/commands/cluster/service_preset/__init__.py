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
"""Unified service preset commands (vdeployer-web /service-presets)."""

from v8x import AsyncTyper

from .create import create_service_preset
from .delete import delete_service_preset
from .get import get_service_preset
from .list import list_service_presets

# Create the service-preset command group
service_preset_app = AsyncTyper(
    name="service-preset",
    help="Manage unified service presets (inference, trainjob, user-service, session).",
    invoke_without_command=True,
    no_args_is_help=True,
)

service_preset_app.command("create")(create_service_preset)
service_preset_app.command("delete")(delete_service_preset)
service_preset_app.command("get")(get_service_preset)
service_preset_app.command("list")(list_service_presets)
