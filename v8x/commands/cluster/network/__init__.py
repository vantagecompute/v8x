# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cluster network management commands."""

from v8x import AsyncTyper

from .create import create_network
from .delete import delete_network
from .get import get_network
from .list import list_networks
from .update import update_network

network_app = AsyncTyper(
    name="network",
    help="Manage Multus networks on a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

network_app.command("create")(create_network)
network_app.command("delete")(delete_network)
network_app.command("get")(get_network)
network_app.command("list")(list_networks)
network_app.command("update")(update_network)
