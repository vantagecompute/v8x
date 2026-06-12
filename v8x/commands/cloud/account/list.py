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
"""List cloud accounts command."""

import typer
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort


@handle_abort
@attach_settings
@attach_persona
async def list_command(
    ctx: typer.Context,
    provider: str = typer.Option(
        None,
        "--provider",
        help="Filter by cloud provider (e.g., aws, gcp, azure).",
    ),
) -> None:
    """List all cloud accounts registered in your organization.

    Cloud accounts are organization-level registrations of cloud provider
    credentials (e.g., AWS IAM roles, GCP service accounts).

    Examples:
        v8x cloud account list
        v8x cloud account list --provider aws
    """
    try:
        # Fetch cloud accounts from API
        accounts = await cloud_account_sdk.list(ctx)

        # Filter by provider if specified
        if provider:
            accounts = [acc for acc in accounts if acc.provider.lower() == provider.lower()]

        if not accounts:
            if provider:
                ctx.obj.formatter.render_list(
                    data=[],
                    resource_name="Cloud Accounts",
                    empty_message=f"No cloud accounts found for provider '{provider}'.",
                )
            else:
                ctx.obj.formatter.render_list(
                    data=[],
                    resource_name="Cloud Accounts",
                    empty_message="No cloud accounts found.",
                )
            return

        # Convert to dict format for the formatter
        accounts_data = []
        for account in accounts:
            account_dict = {
                "id": account.id,
                "name": account.name,
                "provider": account.provider_display,
                "description": account.description or "N/A",
                "assisted": "Yes" if account.assisted_cloud_account else "No",
                "in_use": "Yes" if account.in_use else "No",
            }
            accounts_data.append(account_dict)

        ctx.obj.formatter.render_list(
            data=accounts_data,
            resource_name="Cloud Accounts",
            empty_message="No cloud accounts found.",
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="An unexpected error occurred while listing cloud accounts.",
            details={"error": str(e)},
        )
        raise typer.Exit(code=1)
