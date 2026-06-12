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
"""Get cloud account command."""

import typer
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort


def _obfuscate_sensitive_attributes(attributes: dict | None) -> dict:
    """Obfuscate attributes containing 'cert' or 'key' in their name."""
    if not attributes:
        return {}
    result = {}
    for k, v in attributes.items():
        if "cert" in k.lower() or "key" in k.lower():
            result[k] = "********"
        else:
            result[k] = v
    return result


@handle_abort
@attach_settings
@attach_persona
async def get_command(
    ctx: typer.Context,
    account_id: int = typer.Argument(
        ...,
        help="ID of the cloud account to retrieve.",
    ),
) -> None:
    """Get details of a specific cloud account.

    Displays all information about a cloud account including its
    provider-specific attributes.

    Examples:
        v8x cloud account get 1
    """
    try:
        # Fetch cloud account from API
        account = await cloud_account_sdk.get(ctx, account_id)

        if not account:
            raise Abort(
                f"Cloud account with ID '{account_id}' not found.",
                subject="Cloud Account Not Found",
                log_message=f"Cloud account {account_id} not found",
            )

        # Build data dict for formatter
        account_data = {
            "id": account.id,
            "name": account.name,
            "provider": account.provider,
            "provider_display": account.provider_display,
            "description": account.description or "N/A",
            "assisted_cloud_account": account.assisted_cloud_account,
            "attributes": _obfuscate_sensitive_attributes(account.attributes),
            "in_use": account.in_use,
            "created_at": (account.created_at.isoformat() if account.created_at else "N/A"),
            "updated_at": (account.updated_at.isoformat() if account.updated_at else "N/A"),
        }

        # Add provider-specific attributes
        if account.provider.lower() == "aws":
            if account.aws_role_arn:
                account_data["aws_role_arn"] = account.aws_role_arn
            if account.aws_region:
                account_data["aws_region"] = account.aws_region
        elif account.provider.lower() == "gcp":
            if account.gcp_project_id:
                account_data["gcp_project_id"] = account.gcp_project_id
            if account.gcp_service_account:
                account_data["gcp_service_account"] = account.gcp_service_account
        elif account.provider.lower() == "azure":
            if account.azure_subscription_id:
                account_data["azure_subscription_id"] = account.azure_subscription_id
            if account.azure_tenant_id:
                account_data["azure_tenant_id"] = account.azure_tenant_id

        ctx.obj.formatter.render_get(
            data=account_data,
            resource_name="Cloud Account",
            resource_id=str(account_id),
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="An unexpected error occurred while getting cloud account.",
            details={"error": str(e)},
        )
        raise typer.Exit(code=1)
