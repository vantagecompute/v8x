# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NVIDIA Dynamo deployment commands."""

from v8x import AsyncTyper

from .create import create_dynamo
from .delete import delete_dynamo
from .get import get_dynamo
from .list import list_dynamos
from .status import status_dynamo

dynamo_app = AsyncTyper(
    name="dynamo",
    help="Manage NVIDIA Dynamo model deployments on a cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

dynamo_app.command("status")(status_dynamo)
dynamo_app.command("create")(create_dynamo)
dynamo_app.command("list")(list_dynamos)
dynamo_app.command("get")(get_dynamo)
dynamo_app.command("delete")(delete_dynamo)
