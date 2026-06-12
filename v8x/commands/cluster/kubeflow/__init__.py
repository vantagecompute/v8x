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
"""Kubeflow management commands for v8x.

Provides operations for deploying and managing Kubeflow on a
Vantage K8s cluster. Commands communicate with the vdeployer-web
API running inside the target cluster.

Usage:
    v8x cluster kubeflow create --cluster my-cluster
    v8x cluster kubeflow get --cluster my-cluster
    v8x cluster kubeflow delete --cluster my-cluster
"""

from v8x import AsyncTyper

from .create import create_kubeflow
from .delete import delete_kubeflow
from .get import get_kubeflow

kubeflow_app = AsyncTyper(
    name="kubeflow",
    help="Manage Kubeflow ML platform on a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

kubeflow_app.command("create")(create_kubeflow)
kubeflow_app.command("get")(get_kubeflow)
kubeflow_app.command("delete")(delete_kubeflow)
