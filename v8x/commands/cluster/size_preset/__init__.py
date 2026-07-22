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
"""Size preset commands (vdeployer-web /size-preset)."""

from v8x import AsyncTyper

from .create import create_size_preset
from .delete import delete_size_preset
from .get import get_size_preset
from .list import list_size_presets

# Create the size-preset command group
size_preset_app = AsyncTyper(
    name="size-preset",
    help="Manage size presets (pod shapes: cpu/memory/gpu/compute pool) per workload catalog.",
    invoke_without_command=True,
    no_args_is_help=True,
)

size_preset_app.command("create")(create_size_preset)
size_preset_app.command("delete")(delete_size_preset)
size_preset_app.command("get")(get_size_preset)
size_preset_app.command("list")(list_size_presets)
