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
"""Cluster management commands for v8x."""

from v8x import AsyncTyper

from .compute_pool import compute_pool_app
from .create import create_cluster
from .delete import delete_cluster
from .extend import extend_cluster
from .federation import federation_app
from .get import get_cluster
from .inference_endpoint import inference_endpoint_app
from .inference_preset import inference_preset_app
from .kubeflow import kubeflow_app
from .list import list_clusters
from .model_registry import model_registry_app
from .namespace import namespace_app
from .network import network_app
from .secret import secret_app
from .service import service_app
from .service_preset import service_preset_app
from .slurm import slurm_app
from .update import update_cluster
from .workspace_preset import workspace_preset_app

# Create the cluster command group
cluster_app = AsyncTyper(
    name="cluster",
    help="Manage Vantage compute clusters for high-performance computing workloads.",
    invoke_without_command=True,
    no_args_is_help=True,
)

# Register subcommands directly
cluster_app.command("create")(create_cluster)
cluster_app.command("delete")(delete_cluster)
cluster_app.command("extend")(extend_cluster)
cluster_app.command("get")(get_cluster)
cluster_app.command("list")(list_clusters)
cluster_app.command("update")(update_cluster)

# Add nested command groups
cluster_app.add_typer(compute_pool_app, name="compute-pool")
cluster_app.add_typer(federation_app, name="federation")
cluster_app.add_typer(inference_preset_app, name="preset")
cluster_app.add_typer(inference_endpoint_app, name="inference-endpoint")
cluster_app.add_typer(model_registry_app, name="model-registry")
cluster_app.add_typer(namespace_app, name="namespace")
cluster_app.add_typer(network_app, name="network")
cluster_app.add_typer(kubeflow_app, name="kubeflow")
cluster_app.add_typer(secret_app, name="secret")
cluster_app.add_typer(service_app, name="service")
cluster_app.add_typer(service_preset_app, name="service-preset")
cluster_app.add_typer(slurm_app, name="slurm")
cluster_app.add_typer(workspace_preset_app, name="workspace-preset")
