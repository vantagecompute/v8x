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
"""Workspace preset management commands for Vantage clusters."""

from v8x import AsyncTyper

from .create import create_workspace_preset
from .delete import delete_workspace_preset
from .get import get_workspace_preset
from .list import list_workspace_presets

workspace_preset_app = AsyncTyper(
    name="workspace-preset",
    help="Manage workspace presets (WorkspaceKinds) that define IDE templates for Kubeflow workspaces.",
    invoke_without_command=True,
    no_args_is_help=True,
)

workspace_preset_app.command("create")(create_workspace_preset)
workspace_preset_app.command("delete")(delete_workspace_preset)
workspace_preset_app.command("get")(get_workspace_preset)
workspace_preset_app.command("list")(list_workspace_presets)
