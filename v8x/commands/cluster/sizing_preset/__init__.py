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
"""Sizing preset commands (vdeployer-web /size-preset)."""

from v8x import AsyncTyper

from .create import create_sizing_preset
from .delete import delete_sizing_preset
from .get import get_sizing_preset
from .list import list_sizing_presets

# Create the sizing-preset command group
sizing_preset_app = AsyncTyper(
    name="sizing-preset",
    help="Manage sizing presets (pod shapes: cpu/memory/gpu/compute pool) per workload catalog.",
    invoke_without_command=True,
    no_args_is_help=True,
)

sizing_preset_app.command("create")(create_sizing_preset)
sizing_preset_app.command("delete")(delete_sizing_preset)
sizing_preset_app.command("get")(get_sizing_preset)
sizing_preset_app.command("list")(list_sizing_presets)
