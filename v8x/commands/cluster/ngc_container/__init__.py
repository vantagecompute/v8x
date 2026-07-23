# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NGC framework container catalog commands."""

from v8x import AsyncTyper

from .get import get_ngc_container
from .list import list_ngc_containers

ngc_container_app = AsyncTyper(
    name="ngc-container",
    help="Browse the curated NGC framework container catalog.",
    invoke_without_command=True,
    no_args_is_help=True,
)

ngc_container_app.command("list")(list_ngc_containers)
ngc_container_app.command("get")(get_ngc_container)
