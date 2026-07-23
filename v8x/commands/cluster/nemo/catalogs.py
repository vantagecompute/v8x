# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""NeMo microservices catalog passthrough commands.

The payload schemas are owned by the installed NeMo microservices version —
responses are rendered as JSON verbatim rather than tabulated.
"""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nvidia_catalogs import nemo_catalog_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

_ClusterOpt = Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")]


async def _render_catalog(ctx: typer.Context, response, error_message: str) -> None:
    """Render a NeMo catalog response as JSON (verbatim passthrough)."""
    if response.status_code != 200:
        raise Abort(f"Failed: {response.text}", subject="API Error")

    data = response.json()
    if ctx.obj.json_output:
        print(json.dumps(data, default=str))
        return
    ctx.obj.console.print_json(json.dumps(data, default=str))


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def customization_configs(ctx: typer.Context, cluster_name: _ClusterOpt):
    """List NeMo Customizer fine-tuning recipes (model x technique).

    Examples:
        v8x cluster nemo customization-configs -c my-cluster
    """
    try:
        response = await nemo_catalog_sdk.customization_configs(ctx, cluster_name=cluster_name)
        await _render_catalog(ctx, response, "customization configs")
    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NeMo customization configs.",
            details={"error": str(e)},
        )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def customization_targets(ctx: typer.Context, cluster_name: _ClusterOpt):
    """List NeMo Customizer fine-tunable base models.

    Examples:
        v8x cluster nemo customization-targets -c my-cluster
    """
    try:
        response = await nemo_catalog_sdk.customization_targets(ctx, cluster_name=cluster_name)
        await _render_catalog(ctx, response, "customization targets")
    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NeMo customization targets.",
            details={"error": str(e)},
        )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def evaluation_configs(ctx: typer.Context, cluster_name: _ClusterOpt):
    """List NeMo Evaluator configs.

    Examples:
        v8x cluster nemo evaluation-configs -c my-cluster
    """
    try:
        response = await nemo_catalog_sdk.evaluation_configs(ctx, cluster_name=cluster_name)
        await _render_catalog(ctx, response, "evaluation configs")
    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list NeMo evaluation configs.",
            details={"error": str(e)},
        )
