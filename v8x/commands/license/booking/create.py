# Copyright 2025 Vantage Compute Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create license booking command using the Vantage REST API."""

import json
from pathlib import Path
from typing import Optional

import typer

from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import (
    create_vantage_rest_client,
)


@attach_settings
@handle_abort
async def create_booking(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Booking name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Booking description"
    ),
    json_file: Optional[Path] = typer.Option(
        None, "--json-file", "-f", help="JSON file with booking data"
    ),
):
    """Create a new license booking."""
    create_vantage_rest_client(ctx)
    try:
        if json_file:
            if not json_file.exists():
                typer.echo(f"Error: File {json_file} does not exist", err=True)
                raise typer.Exit(1)
            with open(json_file, "r") as f:
                data = json.load(f)
        else:
            if not name:
                typer.echo("Error: --name is required when not using --json-file", err=True)
                raise typer.Exit(1)
            data = {"name": name}
            if description:
                data["description"] = description

        booking = await ctx.obj.rest_client.post("/bookings", json=data)

        # Use UniversalOutputFormatter for consistent create rendering
        from v8x.render import UniversalOutputFormatter

        formatter = UniversalOutputFormatter(
            console=ctx.obj.console, json_output=ctx.obj.json_output
        )
        formatter.render_create(
            data=booking,
            resource_name="License Booking",
            success_message="License booking created successfully!",
        )
    finally:
        await ctx.obj.rest_client.close()
