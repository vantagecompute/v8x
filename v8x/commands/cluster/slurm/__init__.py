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
"""Slurm cluster management commands for v8x.

Provides CRUD operations for managing multiple Slurm clusters within a
single Vantage K8s cluster. Commands communicate with the vdeployer-web
API running inside the target cluster.

Usage:
    v8x cluster slurm list --cluster my-cluster
    v8x cluster slurm get hpc-prod --cluster my-cluster
    v8x cluster slurm create hpc-prod --cluster my-cluster --control-node-group slurm-admin --partition cpu:slurm-compute:default
    v8x cluster slurm delete hpc-prod --cluster my-cluster
    v8x cluster slurm update hpc-prod --cluster my-cluster
"""

from v8x import AsyncTyper

from .create import create_slurm_cluster
from .delete import delete_slurm_cluster
from .get import get_slurm_cluster
from .list import list_slurm_clusters
from .update import update_slurm_cluster

slurm_app = AsyncTyper(
    name="slurm",
    help="Manage Slurm clusters within a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

slurm_app.command("create")(create_slurm_cluster)
slurm_app.command("delete")(delete_slurm_cluster)
slurm_app.command("get")(get_slurm_cluster)
slurm_app.command("list")(list_slurm_clusters)
slurm_app.command("update")(update_slurm_cluster)
