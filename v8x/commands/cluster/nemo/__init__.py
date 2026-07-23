# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NeMo microservices catalog commands."""

from v8x import AsyncTyper

from .catalogs import customization_configs, customization_targets, evaluation_configs

nemo_app = AsyncTyper(
    name="nemo",
    help="Browse the in-cluster NeMo microservices catalogs (Customizer / Evaluator).",
    invoke_without_command=True,
    no_args_is_help=True,
)

nemo_app.command("customization-configs")(customization_configs)
nemo_app.command("customization-targets")(customization_targets)
nemo_app.command("evaluation-configs")(evaluation_configs)
