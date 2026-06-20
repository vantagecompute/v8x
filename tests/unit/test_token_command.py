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

import json
from types import SimpleNamespace

import pytest
import typer

import v8x.auth as auth_module
import v8x.main as main_module
from v8x import cache as token_cache
from v8x.schemas import TokenSet


def _make_context(profile: str = "default") -> SimpleNamespace:
    return SimpleNamespace(
        obj=SimpleNamespace(
            profile=profile,
            json_output=False,
            verbose=False,
            formatter=None,
        )
    )


def test_token_cache_round_trips_id_token(tmp_path, monkeypatch):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)

    token_cache.save_tokens_to_cache(
        "default",
        TokenSet(
            access_token="access-token",
            refresh_token="refresh-token",
            id_token="id-token",
        ),
    )

    loaded_tokens = token_cache.load_tokens_from_cache("default")

    assert loaded_tokens.access_token == "access-token"
    assert loaded_tokens.refresh_token == "refresh-token"
    assert loaded_tokens.id_token == "id-token"


def test_token_cache_allows_missing_id_token(tmp_path, monkeypatch):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)

    token_cache.save_tokens_to_cache(
        "default",
        TokenSet(access_token="access-token", refresh_token="refresh-token"),
    )

    loaded_tokens = token_cache.load_tokens_from_cache("default")

    assert loaded_tokens.access_token == "access-token"
    assert loaded_tokens.refresh_token == "refresh-token"
    assert loaded_tokens.id_token is None


def test_token_command_prints_id_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)
    token_set = TokenSet(
        access_token="access-token",
        refresh_token="refresh-token",
        id_token="id-token",
    )
    monkeypatch.setattr(main_module, "load_tokens_from_cache", lambda profile: token_set)
    monkeypatch.setattr(main_module, "refresh_token_if_needed", lambda profile, tokens: tokens)

    main_module.token(_make_context(), decode=False, id_token=True)

    assert capsys.readouterr().out == "id-token\n"


def test_token_command_refreshes_on_request(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)
    token_set = TokenSet(
        access_token="access-token",
        refresh_token="refresh-token",
        id_token="id-token",
    )
    refreshed_token_set = TokenSet(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        id_token="new-id-token",
    )
    refresh_call = {}

    def refresh_token(profile, tokens, *, force=False):
        refresh_call["profile"] = profile
        refresh_call["tokens"] = tokens
        refresh_call["force"] = force
        return refreshed_token_set

    monkeypatch.setattr(main_module, "load_tokens_from_cache", lambda profile: token_set)
    monkeypatch.setattr(main_module, "refresh_token_if_needed", refresh_token)

    main_module.token(_make_context("dev"), decode=False, id_token=False, refresh=True)

    assert refresh_call == {"profile": "dev", "tokens": token_set, "force": True}
    assert capsys.readouterr().out == "new-access-token\n"


def test_token_command_decodes_id_token(tmp_path, monkeypatch, capsys, make_token):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)
    id_token = make_token(email="user@example.com", extra_claims={"typ": "ID"})
    token_set = TokenSet(
        access_token=make_token(email="access@example.com"),
        refresh_token="refresh-token",
        id_token=id_token,
    )
    monkeypatch.setattr(main_module, "load_tokens_from_cache", lambda profile: token_set)
    monkeypatch.setattr(main_module, "refresh_token_if_needed", lambda profile, tokens: tokens)

    main_module.token(_make_context(), decode=True, id_token=True)

    decoded_output = json.loads(capsys.readouterr().out)
    assert decoded_output["email"] == "user@example.com"
    assert decoded_output["typ"] == "ID"


def test_token_command_errors_when_id_token_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(token_cache, "USER_TOKEN_CACHE_DIR", tmp_path)
    token_set = TokenSet(access_token="access-token", refresh_token="refresh-token")
    monkeypatch.setattr(main_module, "load_tokens_from_cache", lambda profile: token_set)
    monkeypatch.setattr(main_module, "refresh_token_if_needed", lambda profile, tokens: tokens)

    with pytest.raises(typer.Exit) as exit_info:
        main_module.token(_make_context(), decode=False, id_token=True)

    assert exit_info.value.exit_code == 1


def test_refresh_token_if_needed_force_refreshes_valid_token(monkeypatch, make_token):
    token_set = TokenSet(
        access_token=make_token(email="user@example.com"),
        refresh_token="refresh-token",
        id_token="id-token",
    )
    saved_tokens = {}

    monkeypatch.setattr(auth_module, "USER_CONFIG_FILE", SimpleNamespace(exists=lambda: False))
    monkeypatch.setattr(auth_module, "Settings", lambda **kwargs: object())
    monkeypatch.setattr(
        auth_module,
        "refresh_access_token_standalone",
        lambda tokens, settings: setattr(tokens, "access_token", "new-access-token") or True,
    )
    monkeypatch.setattr(
        auth_module,
        "save_tokens_to_cache",
        lambda profile, tokens: saved_tokens.update({"profile": profile, "tokens": tokens}),
    )

    refreshed_token_set = auth_module.refresh_token_if_needed("default", token_set, force=True)

    assert refreshed_token_set.access_token == "new-access-token"
    assert saved_tokens == {"profile": "default", "tokens": token_set}
