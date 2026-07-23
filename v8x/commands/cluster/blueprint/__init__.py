# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NVIDIA AI Blueprint catalog commands."""

from v8x import AsyncTyper

from .get import get_blueprint
from .list import list_blueprints

blueprint_app = AsyncTyper(
    name="blueprint",
    help="Browse the curated NVIDIA AI Blueprint catalog.",
    invoke_without_command=True,
    no_args_is_help=True,
)

blueprint_app.command("list")(list_blueprints)
blueprint_app.command("get")(get_blueprint)
