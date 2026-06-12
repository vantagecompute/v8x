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
"""External expose subcommand group.

Provides CephFS and NFS subcommands for exposing in-cluster storage
to clients *outside* the Kubernetes cluster.
"""

from v8x import AsyncTyper

from .cephfs import cephfs_app
from .nfs import nfs_app

expose_app = AsyncTyper(name="expose", help="Expose cluster storage to external clients.")
expose_app.add_typer(cephfs_app, name="cephfs")
expose_app.add_typer(nfs_app, name="nfs")

__all__ = ["expose_app"]
