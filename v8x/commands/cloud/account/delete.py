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
"""Delete cloud account command."""

import typer
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort


@handle_abort
@attach_settings
@attach_persona
async def delete_command(
    ctx: typer.Context,
    account_id: int = typer.Argument(
        ...,
        help="ID of the cloud account to delete.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Delete a cloud account.

    WARNING: Deleting a cloud account may affect clusters that use it.
    Accounts that are in use cannot be deleted.

    Examples:
        v8x cloud account delete 1
        v8x cloud account delete 1 --force
    """
    try:
        # First, get the account to show details and check if it exists
        account = await cloud_account_sdk.get(ctx, account_id)

        if not account:
            raise Abort(
                f"Cloud account with ID '{account_id}' not found.",
                subject="Cloud Account Not Found",
                log_message=f"Cloud account {account_id} not found",
            )

        # Check if account is in use
        if account.in_use:
            raise Abort(
                f"Cloud account '{account.name}' (ID: {account_id}) is currently in use by clusters. "
                "Please remove it from all clusters before deleting.",
                subject="Account In Use",
                log_message=f"Cannot delete cloud account {account_id} - in use",
            )

        # Confirm deletion unless --force is used
        if not force:
            ctx.obj.console.print(
                "\n[yellow]Warning:[/yellow] You are about to delete cloud account:"
            )
            ctx.obj.console.print(f"  Name: {account.name}")
            ctx.obj.console.print(f"  Provider: {account.provider_display}")
            ctx.obj.console.print(f"  ID: {account.id}")
            ctx.obj.console.print()

            confirm = typer.confirm("Are you sure you want to delete this cloud account?")
            if not confirm:
                ctx.obj.console.print("[dim]Deletion cancelled.[/dim]")
                raise typer.Exit(code=0)

        # Delete the account
        await cloud_account_sdk.delete(ctx, account_id)

        ctx.obj.formatter.render_delete(
            resource_name="Cloud Account",
            resource_id=str(account_id),
            message=f"Cloud account '{account.name}' has been deleted.",
        )

    except Abort:
        raise
    except typer.Exit:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="An unexpected error occurred while deleting cloud account.",
            details={"error": str(e)},
        )
        raise typer.Exit(code=1)
