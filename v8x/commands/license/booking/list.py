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

"""List license bookings command using the License Manager API."""

from typing import Optional

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
async def list_bookings(
    ctx: typer.Context,
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Search bookings by name or id"
    ),
    sort: Optional[str] = typer.Option(
        None, "--sort", help="Sort by field (name, id, created_at)"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Maximum number of bookings to return"
    ),
    offset: Optional[int] = typer.Option(
        None, "--offset", "-o", help="Number of bookings to skip"
    ),
):
    """List all license bookings."""
    # Use SDK to list license bookings
    response = await license_booking_sdk.list(
        ctx, search=search, sort=sort, limit=limit, offset=offset
    )

    # Use UniversalOutputFormatter for consistent list rendering
    formatter = UniversalOutputFormatter(console=ctx.obj.console, json_output=ctx.obj.json_output)
    formatter.render_list(
        data=response,
        resource_name="License Bookings",
        empty_message="No license bookings found.",
    )
