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

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import v8x.auth as auth_module
from tests.conftest import MockConsole
from v8x.commands.cloud.account import delete as delete_module


@pytest.mark.asyncio
async def test_delete_cloud_account_renders_success_message(monkeypatch) -> None:
    account = SimpleNamespace(
        id=367,
        name="mydatacenter-west",
        provider_display="On Prem",
        in_use=False,
    )
    formatter = MagicMock()
    ctx = SimpleNamespace(
        obj=SimpleNamespace(
            profile="default",
            console=MockConsole(),
            formatter=formatter,
        )
    )

    monkeypatch.setattr(
        auth_module,
        "extract_persona",
        lambda profile: SimpleNamespace(identity_data=SimpleNamespace(email="test@example.com")),
    )
    monkeypatch.setattr(delete_module.cloud_account_sdk, "get", AsyncMock(return_value=account))
    monkeypatch.setattr(delete_module.cloud_account_sdk, "delete", AsyncMock())

    await delete_module.delete_command(ctx, account_id=367, force=True)

    delete_module.cloud_account_sdk.delete.assert_awaited_once_with(ctx, 367)
    formatter.render_delete.assert_called_once_with(
        resource_name="Cloud Account",
        resource_id="367",
        success_message="Cloud account 'mydatacenter-west' has been deleted.",
    )
