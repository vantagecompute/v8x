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

"""Inference preset management commands for Vantage clusters."""

from v8x import AsyncTyper

from .create import create_inference_preset
from .delete import delete_inference_preset
from .get import get_inference_preset
from .list import list_inference_presets

inference_preset_app = AsyncTyper(
    name="preset",
    help="Manage inference presets within a Vantage K8s cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

inference_preset_app.command("create")(create_inference_preset)
inference_preset_app.command("delete")(delete_inference_preset)
inference_preset_app.command("get")(get_inference_preset)
inference_preset_app.command("list")(list_inference_presets)
