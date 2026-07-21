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
"""List configuration presets command."""

from typing import Optional

import typer
from rich.table import Table
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.configuration_preset import (
    CONFIGURATION_PRESET_KINDS,
    configuration_preset_sdk,
)

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


def _summarize_options(options: dict) -> str:
    """One-line summary of the kind-specific options for the table."""
    parts: list[str] = []
    for key, value in options.items():
        if value in (None, [], {}, ""):
            continue
        if key == "sizing_preset":
            continue  # rendered in its own column
        if key == "runtime_ref" and isinstance(value, dict):
            parts.append(f"runtime={value.get('name')}")
        elif key == "service_types" and isinstance(value, list):
            parts.append(f"workloads={','.join(value)}")
        elif isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}={value}")
        else:
            parts.append(key)
    return " ".join(parts)[:64] or "-"


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_configuration_presets(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Option(
            "--cluster",
            "-c",
            help="Name of the parent K8s cluster",
        ),
    ],
    kind: Annotated[
        Optional[str],
        typer.Option(
            "--kind",
            "-k",
            help=f"Filter by preset kind: {', '.join(sorted(CONFIGURATION_PRESET_KINDS))}",
        ),
    ] = None,
):
    """List configuration presets on a Vantage cluster.

    Examples:
        v8x cluster configuration-preset list -c my-cluster
        v8x cluster configuration-preset list -c my-cluster --kind cloud-shell
    """
    console = ctx.obj.console

    try:
        console.print("[dim]Fetching configuration presets...[/dim]")

        response = await configuration_preset_sdk.list(ctx, cluster_name=cluster_name, kind=kind)

        if response.status_code == 200:
            items = response.json().get("items", [])
            if not items:
                console.print("[yellow]No configuration presets found[/yellow]")
                return

            table = Table(title=f"Configuration Presets ({len(items)} total)")
            table.add_column("Kind", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Sizing Preset", style="magenta")
            table.add_column("Options", style="dim")
            table.add_column("Description", style="dim")

            for p in items:
                table.add_row(
                    p.get("kind", "?"),
                    p.get("name", "?"),
                    (p.get("options") or {}).get("sizing_preset") or "",
                    _summarize_options(p.get("options") or {}),
                    (p.get("description") or "")[:48],
                )

            console.print(table)
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to list configuration presets: {error_detail}",
                subject="Preset List Failed",
                log_message=f"Configuration preset list failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list configuration presets.",
            details={"error": str(e)},
        )
