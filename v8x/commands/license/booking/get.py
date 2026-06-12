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

"""Get license booking command using the Vantage REST API."""

import typer
from vantage_sdk.license import license_booking_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.render import UniversalOutputFormatter
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client(base_path="/lm")
async def get_booking(
    ctx: typer.Context, booking_id: str = typer.Argument(..., help="Booking ID")
):
    """Get a specific license booking by ID."""
    # Use SDK to get license booking
    response = await license_booking_sdk.get(ctx, booking_id)

    # Use UniversalOutputFormatter for consistent get rendering
    formatter = UniversalOutputFormatter(console=ctx.obj.console, json_output=ctx.obj.json_output)
    formatter.render_get(data=response, resource_name="License Booking", resource_id=booking_id)
