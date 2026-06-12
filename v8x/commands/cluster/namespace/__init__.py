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
"""Namespace management commands for Vantage clusters."""

from v8x import AsyncTyper

from .create import create_namespace
from .delete import delete_namespace
from .get import get_namespace
from .list import list_namespaces

namespace_app = AsyncTyper(
    name="namespace",
    help="Manage namespaces on a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

namespace_app.command("create")(create_namespace)
namespace_app.command("delete")(delete_namespace)
namespace_app.command("get")(get_namespace)
namespace_app.command("list")(list_namespaces)
