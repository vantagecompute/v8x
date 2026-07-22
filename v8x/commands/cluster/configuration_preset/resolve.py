# Copyright (C) 2025 Vantage Compute Corporation
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""Resolve (preview) the effective configuration of a configuration preset."""

import json
from typing import Optional

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.configuration_preset import configuration_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def resolve_configuration_preset(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Preset name"),
    ],
    cluster_name: Annotated[
        str,
        typer.Option("--cluster", "-c", help="Name of the parent K8s cluster"),
    ],
    kind: Annotated[
        str,
        typer.Option("--kind", "-k", help="Configuration preset kind (e.g. kserve, trainjob)"),
    ] = "kserve",
    size_preset: Annotated[
        Optional[str],
        typer.Option(
            "--size-preset",
            "-p",
            help="Request-level size preset (overrides the preset's bundle)",
        ),
    ] = None,
    overrides_json: Annotated[
        Optional[str],
        typer.Option(
            "--overrides-json",
            help="Raw JSON overrides (same shape as the preset's options); "
            "env merges by name, args append, scalars replace",
        ),
    ] = None,
):
    r"""Preview the effective configuration a workload create would resolve to.

    Runs the server-side merge (built-in defaults ⊕ preset options ⊕
    overrides) without creating anything — the same resolution every
    workload create endpoint performs.

    Examples:
        v8x cluster configuration-preset resolve gpu-medium -c my-cluster -k kserve

        v8x cluster configuration-preset resolve gpu-medium -c my-cluster -k kserve \\
            --overrides-json '{"env": {"LOG_LEVEL": "debug"}}'
    """
    console = ctx.obj.console

    overrides = None
    if overrides_json:
        try:
            overrides = json.loads(overrides_json)
        except json.JSONDecodeError as exc:
            raise Abort(
                f"--overrides-json is not valid JSON: {exc}",
                subject="Invalid Overrides",
            ) from exc
        if not isinstance(overrides, dict):
            raise Abort(
                "--overrides-json must be a JSON object (e.g. {...}).",
                subject="Invalid Overrides",
            )

    try:
        response = await configuration_preset_sdk.resolve(
            ctx,
            cluster_name=cluster_name,
            kind=kind,
            name=name,
            size_preset=size_preset,
            overrides=overrides,
        )
        if response.status_code == 200:
            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                console.print(
                    f"[green]✓[/green] Effective configuration for "
                    f"[green]'{data.get('name', name)}'[/green] (kind={data.get('kind', kind)}):"
                )
                console.print_json(json.dumps(data, default=str))
        else:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to resolve configuration preset: {detail}",
                subject="Preset Resolve Failed",
            )
    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"Failed to resolve configuration preset '{name}'.",
            details={"error": str(e)},
        )
