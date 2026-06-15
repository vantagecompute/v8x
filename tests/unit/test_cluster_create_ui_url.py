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

from types import SimpleNamespace

from v8x.commands.cluster.create import _build_cluster_ui_url


def test_build_cluster_ui_url_uses_vantage_url_and_client_id() -> None:
    cluster = SimpleNamespace(
        name="cluster-name",
        client_id="mult-demo-bdx-arm64-22e25a1f-bdea-48fc-b131-ec7aedbaae82",
    )

    assert _build_cluster_ui_url(cluster, "https://app.vantagecompute.ai/") == (
        "https://app.vantagecompute.ai/compute/clusters/"
        "mult-demo-bdx-arm64-22e25a1f-bdea-48fc-b131-ec7aedbaae82"
    )


def test_build_cluster_ui_url_falls_back_to_name() -> None:
    cluster = SimpleNamespace(name="cluster/name", client_id=None)

    assert _build_cluster_ui_url(cluster, "https://app.dev.vantagecompute.ai") == (
        "https://app.dev.vantagecompute.ai/compute/clusters/cluster%2Fname"
    )
