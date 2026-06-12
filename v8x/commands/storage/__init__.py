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
"""Storage management commands for v8x.

Manages PersistentVolumeClaims and storage systems via the vdeployer-web API.

Subcommand groups:
  system  – Manage storage system deployments (CephFS, CephNFS, etc.)
  expose  – Expose cluster storage to external clients (CephFS / NFS)
  import  – Import storage into cluster namespaces (internal / CephFS / NFS)

Individual PVC commands:
  create, delete, get, list, list-available, attach, detach, update
"""

from v8x import AsyncTyper

from .create import create_storage
from .delete import delete_storage
from .external_expose import expose_app
from .get import get_storage
from .list import list_storage
from .list_available import list_available_storage
from .namespace_import import import_app
from .system import system_app

# ---------------------------------------------------------------------------
# Storage command group
# ---------------------------------------------------------------------------

storage_app = AsyncTyper(
    name="storage",
    help="Manage storage: PVCs, imports, exposes, and storage systems.",
    invoke_without_command=True,
    no_args_is_help=True,
)

# Subcommand groups
storage_app.add_typer(system_app, name="system")
storage_app.add_typer(expose_app, name="expose")
storage_app.add_typer(import_app, name="import")

# Individual PVC commands
storage_app.command("create")(create_storage)
storage_app.command("delete")(delete_storage)
storage_app.command("get")(get_storage)
storage_app.command("list")(list_storage)
storage_app.command("list-available")(list_available_storage)
