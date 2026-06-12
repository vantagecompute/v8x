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
"""Model registry commands."""

from v8x import AsyncTyper

from .create import create_model
from .delete import delete_model_version
from .get import get_model
from .job import get_model_job
from .list import list_models
from .search import search_models
from .update import update_model
from .versions import list_model_versions

model_registry_app = AsyncTyper(
    name="model-registry",
    help="Manage models in the cluster model registry (onboard, list, version, delete).",
    invoke_without_command=True,
    no_args_is_help=True,
)

model_registry_app.command("create")(create_model)
model_registry_app.command("list")(list_models)
model_registry_app.command("get")(get_model)
model_registry_app.command("update")(update_model)
model_registry_app.command("delete")(delete_model_version)
model_registry_app.command("versions")(list_model_versions)
model_registry_app.command("search")(search_models)
model_registry_app.command("job")(get_model_job)
