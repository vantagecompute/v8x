# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NVIDIA NIM deployment commands."""

from v8x import AsyncTyper

from .catalog import catalog_nim, versions_nim
from .create import create_nim
from .delete import delete_nim
from .get import get_nim
from .list import list_nims

nim_app = AsyncTyper(
    name="nim",
    help="Manage NVIDIA NIM deployments on a cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

nim_app.command("catalog")(catalog_nim)
nim_app.command("versions")(versions_nim)
nim_app.command("create")(create_nim)
nim_app.command("list")(list_nims)
nim_app.command("get")(get_nim)
nim_app.command("delete")(delete_nim)
