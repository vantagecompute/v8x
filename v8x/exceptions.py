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
"""Exception handling and error management for the v8x."""

import inspect
import logging
from functools import wraps
from typing import TYPE_CHECKING

import snick
import typer
from rich.console import Console
from rich.panel import Panel
from vantage_sdk.exceptions import (
    Abort,
    AuthenticationError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "get_console_from_context",
    "get_console_from_cli_context",
    "handle_abort",
]

if TYPE_CHECKING:
    from v8x.schemas import CliContext

# Enables prettified traceback printing via rich - we'll install this conditionally
# traceback.install()  # Commented out to avoid showing tracebacks in normal mode


def get_console_from_context(ctx: typer.Context) -> Console:
    """Get console from typer context, falling back to new Console if not available."""
    if hasattr(ctx.obj, "console") and ctx.obj.console is not None:
        return ctx.obj.console
    return Console()


def get_console_from_cli_context(ctx: "CliContext") -> Console:
    """Get console from CliContext, falling back to new Console if not available."""
    if ctx.console is not None:
        return ctx.console
    return Console()


def _handle_authentication_error(auth_err: AuthenticationError, console: Console) -> None:
    """Handle authentication errors with consistent messaging."""
    message = (
        "Authentication failed. Your token may be expired or invalid.\n\n"
        "Please run 'v8x login' to authenticate again."
    )
    console.print()
    console.print(Panel(message, title="[red]Authentication Required"))
    console.print()
    logger.error(f"Authentication error: {auth_err}")
    raise typer.Exit(code=1)


def _handle_abort_error(err: Abort, console: Console) -> None:
    """Handle abort errors with consistent messaging."""
    if not err.warn_only:
        if err.log_message is not None:
            logger.debug(err.log_message)

        if err.original_error is not None:
            logger.debug(f"Original exception: {err.original_error}")

    panel_kwargs = {}
    if err.subject is not None:
        panel_kwargs["title"] = f"[red]{err.subject}"
    message = snick.dedent(err.message)

    console.print()
    console.print(Panel(message, **panel_kwargs))
    console.print()
    raise typer.Exit(code=1)


def handle_abort(func):
    """Handle abort exceptions in decorated functions."""
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except AuthenticationError as auth_err:
                # Get console from CliContext
                console = (
                    get_console_from_context(args[0])
                    if args and hasattr(args[0], "obj")
                    else Console()
                )
                _handle_authentication_error(auth_err, console)
            except Abort as err:
                # Get console from CliContext
                console = (
                    get_console_from_context(args[0])
                    if args and hasattr(args[0], "obj")
                    else Console()
                )
                _handle_abort_error(err, console)

        return async_wrapper
    else:

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AuthenticationError as auth_err:
                # Get console from CliContext
                console = (
                    get_console_from_context(args[0])
                    if args and hasattr(args[0], "obj")
                    else Console()
                )
                _handle_authentication_error(auth_err, console)
            except Abort as err:
                # Get console from CliContext
                console = (
                    get_console_from_context(args[0])
                    if args and hasattr(args[0], "obj")
                    else Console()
                )
                _handle_abort_error(err, console)

        return wrapper
