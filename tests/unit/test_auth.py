# Copyright 2025 Vantage Compute Corporation

import pytest

import v8x.auth as auth_module
from v8x.schemas import TokenSet


def test_validate_token_reports_unassigned_organization(make_token):
    token_set = TokenSet(
        access_token=make_token(email="user@example.com"),
        refresh_token="refresh-token",
    )

    with pytest.raises(auth_module.Abort) as err_info:
        auth_module.validate_token_and_extract_identity(token_set)

    assert "not assigned to an organization" in err_info.value.message
