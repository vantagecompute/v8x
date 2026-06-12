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

"""Delete license booking command using the Vantage REST API."""

import typer

from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import (
    create_vantage_rest_client,
)


@attach_settings
@handle_abort
async def delete_booking(
    ctx: typer.Context, booking_id: str = typer.Argument(..., help="Booking ID")
):
    """Delete a license booking."""
    create_vantage_rest_client(ctx)
    try:
        await ctx.obj.rest_client.delete(f"/bookings/{booking_id}")

        # Use UniversalOutputFormatter for consistent delete rendering
        from v8x.render import UniversalOutputFormatter

        formatter = UniversalOutputFormatter(
            console=ctx.obj.console, json_output=ctx.obj.json_output
        )
        formatter.render_delete(
            resource_name="License Booking",
            resource_id=booking_id,
            success_message=f"License booking '{booking_id}' deleted successfully!",
        )
    finally:
        await ctx.obj.rest_client.close()
