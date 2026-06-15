# Copyright (C) 2026 Vantage Compute Corporation
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
"""LXD Juju extension app entry point."""

import typer
from vantage_sdk.cluster.schema import Cluster
from vantage_sdk.exceptions import Abort


async def create(ctx: typer.Context, cluster: Cluster, verbose: bool = False) -> typer.Exit:
    """Extend an LXD cluster with Juju-managed compute nodes."""
    raise Abort(
        "The juju-ext deployment workflow is not implemented in this v8x package yet.",
        subject="Extension Not Implemented",
        log_message=f"juju-ext invoked for cluster {cluster.name}",
    )
