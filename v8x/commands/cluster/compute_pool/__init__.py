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
"""Compute pool management commands for Vantage clusters."""

from v8x import AsyncTyper

from .create import create_compute_pool
from .delete import delete_compute_pool
from .get import get_compute_pool
from .list import list_compute_pools

compute_pool_app = AsyncTyper(
    name="compute-pool",
    help="Manage compute pools (autoscaler pools) within a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

compute_pool_app.command("create")(create_compute_pool)
compute_pool_app.command("delete")(delete_compute_pool)
compute_pool_app.command("get")(get_compute_pool)
compute_pool_app.command("list")(list_compute_pools)
