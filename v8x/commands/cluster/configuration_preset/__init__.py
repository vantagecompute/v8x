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
"""Configuration preset commands (vdeployer-web /configuration-presets)."""

from v8x import AsyncTyper

from .create import create_configuration_preset
from .delete import delete_configuration_preset
from .get import get_configuration_preset
from .list import list_configuration_presets
from .resolve import resolve_configuration_preset

# Create the configuration-preset command group
configuration_preset_app = AsyncTyper(
    name="configuration-preset",
    help="Manage configuration presets (kind-specific CR-assembly options; sizing lives in sizing-presets).",
    invoke_without_command=True,
    no_args_is_help=True,
)

configuration_preset_app.command("create")(create_configuration_preset)
configuration_preset_app.command("delete")(delete_configuration_preset)
configuration_preset_app.command("get")(get_configuration_preset)
configuration_preset_app.command("list")(list_configuration_presets)
configuration_preset_app.command("resolve")(resolve_configuration_preset)
