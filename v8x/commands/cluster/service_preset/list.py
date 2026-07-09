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
"""List service presets command."""

from typing import Optional

import typer
from rich.table import Table
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.service_preset import PRESET_KINDS, service_preset_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def list_service_presets(
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
            help=f"Filter by preset kind: {', '.join(sorted(PRESET_KINDS))}",
        ),
    ] = None,
):
    """List service presets on a Vantage cluster.

    Examples:
        v8x cluster service-preset list -c my-cluster
        v8x cluster service-preset list -c my-cluster --kind user-service
    """
    console = ctx.obj.console

    try:
        console.print("[dim]Fetching service presets...[/dim]")

        response = await service_preset_sdk.list(ctx, cluster_name=cluster_name, kind=kind)

        if response.status_code == 200:
            items = response.json().get("items", [])
            if not items:
                console.print("[yellow]No presets found[/yellow]")
                return

            table = Table(title=f"Service Presets ({len(items)} total)")
            table.add_column("Kind", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("CPU")
            table.add_column("Memory")
            table.add_column("GPU")
            table.add_column("Node Group", style="dim")
            table.add_column("Description", style="dim")

            for p in items:
                sizing = (p.get("options") or {}).get("sizing") or {}
                gpu = sizing.get("gpu") or {}
                table.add_row(
                    p.get("kind", "?"),
                    p.get("name", "?"),
                    str(sizing.get("cpu", "-")),
                    str(sizing.get("memory", "-")),
                    str(gpu.get("count", 0) or "-"),
                    sizing.get("node_group") or "-",
                    (p.get("description") or "")[:48],
                )

            console.print(table)
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            raise Abort(
                f"Failed to list presets: {error_detail}",
                subject="Preset List Failed",
                log_message=f"Preset list failed: {error_detail}",
            )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to list service presets.",
            details={"error": str(e)},
        )
