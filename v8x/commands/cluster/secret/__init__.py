# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Secret management commands."""

from v8x import AsyncTyper

from .create import create_secret
from .delete import delete_secret
from .get import get_secret
from .list import list_secrets
from .test import test_secret

secret_app = AsyncTyper(
    name="secret",
    help="Manage secrets (HuggingFace tokens, S3 credentials) in your profile namespace.",
    invoke_without_command=True,
    no_args_is_help=True,
)

secret_app.command("create")(create_secret)
secret_app.command("list")(list_secrets)
secret_app.command("get")(get_secret)
secret_app.command("delete")(delete_secret)
secret_app.command("test")(test_secret)
