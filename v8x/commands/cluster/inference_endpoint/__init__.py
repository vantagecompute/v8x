# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Inference endpoint commands."""

from v8x import AsyncTyper

from .create import create_inference
from .delete import delete_inference
from .get import get_inference
from .list import list_inferences
from .logs import logs_inference
from .runtimes import list_runtimes
from .start_stop import start_inference, stop_inference

inference_endpoint_app = AsyncTyper(
    name="inference-endpoint",
    help="Manage inference endpoints (predictive & LLM) on a cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

inference_endpoint_app.command("create")(create_inference)
inference_endpoint_app.command("list")(list_inferences)
inference_endpoint_app.command("get")(get_inference)
inference_endpoint_app.command("delete")(delete_inference)
inference_endpoint_app.command("start")(start_inference)
inference_endpoint_app.command("stop")(stop_inference)
inference_endpoint_app.command("logs")(logs_inference)
inference_endpoint_app.command("runtimes")(list_runtimes)
