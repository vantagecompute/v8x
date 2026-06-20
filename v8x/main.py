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
"""Main typer app for v8x."""

# Disable HTTP library logging before any imports that might use httpx
import datetime
import json
import logging
import shutil
import subprocess
from typing import Optional

import typer
from jose import jwt
from rich.console import Console
from rich.panel import Panel
from vantage_sdk.exceptions import Abort

from v8x import AsyncTyper, __version__, setup_logging
from v8x.auth import (
    extract_persona,
    fetch_auth_tokens,
    is_token_expired,
    refresh_token_if_needed,
)
from v8x.cache import clear_token_cache, load_tokens_from_cache, with_cache
from v8x.client import attach_client
from v8x.commands.alias import (
    apps_command,
    cloud_accounts_command,
    clouds_command,
    clusters_command,
    federations_command,
    networks_command,
    profiles_command,
    teams_command,
)
from v8x.commands.app import app_app
from v8x.commands.cloud import cloud_app
from v8x.commands.cluster import cluster_app
from v8x.commands.config import config_app
from v8x.commands.get_kubeconfig import get_kubeconfig
from v8x.commands.job import job_app
from v8x.commands.license import license_app
from v8x.commands.network import network_app
from v8x.commands.profile import profile_app
from v8x.commands.storage import storage_app
from v8x.commands.support_ticket import support_ticket_app
from v8x.commands.team import team_app
from v8x.commands.vdeployer_web import vdeployer_web_app
from v8x.config import (
    attach_settings,
    ensure_default_profile_exists,
    get_active_profile,
)
from v8x.exceptions import handle_abort
from v8x.render import UniversalOutputFormatter
from v8x.schemas import CliContext, Persona, TokenSet
from v8x.utils import get_dev_apps_gh_url

from .constants import V8X_DEV_APPS_DIR

logger = logging.getLogger(__name__)


# os.environ["COLUMNS"] = "200"

logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").disabled = True

app = AsyncTyper(
    name="v8x",
    add_completion=False,
    help="Vantage Compute Command Line Interface",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.command()
@handle_abort
def version(ctx: typer.Context):
    """Show version and exit."""
    if hasattr(ctx.obj, "json_output") and ctx.obj and ctx.obj.json_output:
        import json

        print(json.dumps({"version": __version__}))
    else:
        typer.echo(__version__)


app.command("get-kubeconfig")(get_kubeconfig)


app.add_typer(app_app, name="app")
app.add_typer(cloud_app, name="cloud")
app.add_typer(cluster_app, name="cluster")
app.add_typer(config_app, name="config")
app.add_typer(job_app, name="job")
app.add_typer(license_app, name="license")
app.add_typer(network_app, name="network")
app.add_typer(profile_app, name="profile")
app.add_typer(storage_app, name="storage")
app.add_typer(support_ticket_app, name="support-ticket")
app.add_typer(team_app, name="team")
app.add_typer(vdeployer_web_app, name="vdeployer-web")


@app.callback(invoke_without_command=True)
@handle_abort
def main(ctx: typer.Context):
    """Handle global options for the application."""
    # If no subcommand is invoked, display help
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()

    ensure_default_profile_exists()

    # Get injected parameters from context object if they exist
    profile = getattr(ctx.obj, "profile", None) if hasattr(ctx, "obj") and ctx.obj else None
    verbose = getattr(ctx.obj, "verbose", False) if hasattr(ctx, "obj") and ctx.obj else False
    json_output = (
        getattr(ctx.obj, "json_output", False) if hasattr(ctx, "obj") and ctx.obj else False
    )

    # Use explicit profile if provided, otherwise get the active profile
    active_profile = profile if profile is not None else get_active_profile()

    setup_logging(verbose=verbose)

    # Create a single console instance for the entire application
    # console = Console(width=200)
    console = Console(color_system="auto", force_terminal=True)

    formatter = UniversalOutputFormatter(console=console, json_output=json_output)

    cli_ctx = CliContext(
        profile=active_profile,
        json_output=json_output,
        verbose=verbose,
        console=console,
        formatter=formatter,
    )
    ctx.obj = cli_ctx


@app.command(hidden=True)
@handle_abort
@with_cache
@attach_settings
async def dev_clear(ctx: typer.Context):
    """Clear the v8x dev apps directory."""
    if V8X_DEV_APPS_DIR.exists():
        shutil.rmtree(V8X_DEV_APPS_DIR)
        ctx.obj.console.print(
            f"[green]Successfully cleared dev apps directory at {V8X_DEV_APPS_DIR}[/green]"
        )


@app.command(hidden=True)
@handle_abort
@with_cache
@attach_settings
async def dev_init(ctx: typer.Context):
    """Initialize the v8x dev apps directory by cloning from GitHub."""
    if clone_url := get_dev_apps_gh_url():
        if V8X_DEV_APPS_DIR.exists():
            shutil.rmtree(V8X_DEV_APPS_DIR)
        try:
            _ = subprocess.run(
                [
                    "git",
                    "clone",
                    clone_url,
                    str(V8X_DEV_APPS_DIR),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            ctx.obj.console.print(
                f"[green]Successfully cloned dev apps to {V8X_DEV_APPS_DIR}[/green]"
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone dev apps: {e.stderr}")
            typer.echo(f"Error: Failed to clone repository - {e.stderr}", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("Error: GH_PAT environment variable not found", err=True)
        raise typer.Exit(1)


def _check_existing_login(profile: str) -> Optional[str]:
    """Check if user is already logged in with a valid token.

    Returns:
        Email of logged in user if valid token exists, None otherwise
    """
    try:
        # Try to load tokens from cache
        token_set = load_tokens_from_cache(profile)

        # Check if access token is valid (not expired)
        if token_set.access_token and not is_token_expired(token_set.access_token):
            # Extract email from token for display
            try:
                persona = extract_persona(profile, token_set)
                return persona.identity_data.email
            except Exception as e:
                logger.debug(f"Could not extract persona from existing token: {e}")
                return None

    except Exception as e:
        # Token cache doesn't exist or other error - user not logged in
        logger.debug(f"No valid existing login found: {e}")
        return None

    return None


@app.command()
@handle_abort
@with_cache
@attach_settings
@attach_client
async def login(ctx: typer.Context):
    """Authenticate against the v8x by obtaining an authentication token."""
    formatter = UniversalOutputFormatter(console=ctx.obj.console, json_output=ctx.obj.json_output)

    # Check if user is already logged in with a valid token
    existing_email = _check_existing_login(ctx.obj.profile)
    if existing_email:
        login_data = {
            "profile": ctx.obj.profile,
            "email": existing_email,
            "status": "already_authenticated",
            "message": "Valid token already exists. Run 'v8x logout' first to generate a new token.",
        }

        if ctx.obj.json_output:
            formatter.render_get(
                data=login_data,
                resource_name="Login Status",
                resource_id=ctx.obj.profile,
            )
        else:
            console = ctx.obj.console
            console.print()
            console.print(
                Panel(
                    f"Profile: [bold]{ctx.obj.profile}[/bold]\n\n"
                    f"✅ Valid token already exists for user: [bold cyan]{existing_email}[/bold cyan]\n\n"
                    f"If you want to generate a new token, please run '[bold magenta]v8x logout[/bold magenta]' first.",
                    title="[green]Already Authenticated[/green]",
                    border_style="green",
                )
            )
            console.print()
        return

    token_set: TokenSet = await fetch_auth_tokens(ctx.obj)
    persona: Persona = extract_persona(ctx.obj.profile, token_set)

    login_data = {
        "profile": ctx.obj.profile,
        "email": persona.identity_data.email,
        "client_id": persona.identity_data.client_id,
        "status": "authenticated",
        "message": "Successfully authenticated. You can now use the CLI to interact with Vantage Compute platform.",
    }

    if ctx.obj.json_output:
        formatter.render_create(
            data=login_data,
            resource_name="Login",
            success_message="Successfully authenticated",
        )
    else:
        console = ctx.obj.console
        console.print()
        console.print(
            Panel(
                f"Profile: [bold]{ctx.obj.profile}[/bold]\n\n"
                f"✅ Successful authentication: [bold cyan]{persona.identity_data.email}[/bold cyan]\n\n"
                "You can now use the CLI to interact with Vantage Compute platform.",
                title="[green]Successful Authentication[/green]",
                border_style="green",
            )
        )
        console.print()


@app.command()
@handle_abort
@with_cache
async def logout(ctx: typer.Context):
    """Log out of the v8x and clear saved user credentials."""
    formatter = UniversalOutputFormatter(console=ctx.obj.console, json_output=ctx.obj.json_output)

    existing_email = _check_existing_login(ctx.obj.profile)

    logout_data = {
        "profile": ctx.obj.profile,
        "email": existing_email if existing_email else "Not authenticated",
        "status": "logged_out" if existing_email else "not_authenticated",
        "message": "Please run 'v8x login' to log back in."
        if existing_email
        else "No active session found.",
    }

    if existing_email:
        if ctx.obj.json_output:
            formatter.render_delete(
                resource_name="Login Session",
                resource_id=ctx.obj.profile,
                success_message=f"Successfully signed out user: {existing_email}",
            )
        else:
            console = ctx.obj.console
            console.print()
            console.print(
                Panel(
                    f"Profile: [bold]{ctx.obj.profile}[/bold]\n\n"
                    f"✅ [bold]User:[/bold] {existing_email}\n\n"
                    f"Please run '[bold magenta]v8x login[/bold magenta]' to log back in.",
                    title="[green]Successfully Signed Out[/green]",
                    border_style="green",
                )
            )
            console.print()
    else:
        if ctx.obj.json_output:
            formatter.render_get(
                data=logout_data,
                resource_name="Logout Status",
                resource_id=ctx.obj.profile,
            )

    clear_token_cache(ctx.obj.profile)


@app.command()
@handle_abort
@with_cache
@attach_settings
async def whoami(ctx: typer.Context):
    """Display information about the currently authenticated user."""
    formatter = UniversalOutputFormatter(console=ctx.obj.console, json_output=ctx.obj.json_output)

    try:
        # Extract persona from cached tokens
        persona: Persona = extract_persona(ctx.obj.profile)

        token_info = {}
        token_data: dict[str, object] = {}
        try:
            token_data = jwt.decode(
                persona.token_set.access_token,
                "",  # Empty key is acceptable when verify_signature is False
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_exp": False,  # Don't verify expiration for display
                },
            )

            # Extract additional fields if available
            if "exp" in token_data:
                exp_timestamp = token_data["exp"]
                if isinstance(exp_timestamp, int | float):
                    exp_datetime = datetime.datetime.fromtimestamp(exp_timestamp)
                    token_info["token_expires_at"] = exp_datetime.isoformat()
                    token_info["token_expired"] = exp_datetime < datetime.datetime.now()

            if "iat" in token_data:
                iat_timestamp = token_data["iat"]
                if isinstance(iat_timestamp, int | float):
                    iat_datetime = datetime.datetime.fromtimestamp(iat_timestamp)
                    token_info["token_issued_at"] = iat_datetime.isoformat()

            if "sub" in token_data:
                token_info["user_id"] = token_data["sub"]

            if "name" in token_data:
                token_info["name"] = token_data["name"]

        except Exception as e:
            logger.debug(f"Could not decode token for additional info: {e}")

        # Extract preferred_username and org from token
        if "preferred_username" in token_data:
            token_info["preferred_username"] = token_data["preferred_username"]
        if "organization" in token_data:
            token_info["organization"] = token_data["organization"]

        # Prepare user information
        user_info = {
            "email": persona.identity_data.email,
            "client_id": persona.identity_data.client_id,
            "profile": ctx.obj.profile,
            "logged_in": True,
            **token_info,
        }

        # Raw JSON output for machine consumption
        if ctx.obj.json_output:
            print(json.dumps(user_info, default=str))
            return

        # Use UniversalOutputFormatter to render the user info
        formatter.render_get(
            data=user_info,
            resource_name="Current User",
            resource_id=persona.identity_data.email,
        )

    except Exception as e:
        logger.debug(f"Failed to get user information: {str(e)}")

        error_info = {
            "logged_in": False,
            "error": "Not authenticated or token expired",
            "profile": ctx.obj.profile,
            "message": "Please run 'v8x login' to authenticate",
        }

        if ctx.obj.json_output:
            formatter.render_get(
                data=error_info,
                resource_name="Current User",
                resource_id=ctx.obj.profile,
            )
        else:
            console = ctx.obj.console
            console.print()
            console.print(
                Panel(
                    "❌ Not authenticated or token expired\n\n"
                    f"Current profile: [bold]{ctx.obj.profile}[/bold]\n"
                    f"Please run [bold]v8x login[/bold] to authenticate",
                    title="[red]Authentication Required[/red]",
                    border_style="red",
                )
            )
            console.print()


@app.command()
@handle_abort
@with_cache
async def token(
    ctx: typer.Context,
    decode: bool = typer.Option(
        False, "--decode", "-d", help="Decode and print the JWT token claims"
    ),
    id_token: bool = typer.Option(
        False, "--id", help="Print the ID token instead of the access token"
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Use the refresh token to request a new token before printing",
    ),
):
    """Print the current access token to the terminal."""
    token_set = load_tokens_from_cache(ctx.obj.profile)
    if refresh is True:
        token_set = refresh_token_if_needed(ctx.obj.profile, token_set, force=True)
    else:
        token_set = refresh_token_if_needed(ctx.obj.profile, token_set)
    selected_token = token_set.id_token if id_token else token_set.access_token
    if selected_token is None:
        raise Abort(
            "No ID token is available. Please run `v8x login` to refresh your cached tokens.",
            subject="ID token unavailable",
            log_message="ID token requested but missing from token cache",
        )
    if decode:
        claims = jwt.get_unverified_claims(selected_token)
        typer.echo(json.dumps(claims, indent=2))
    else:
        typer.echo(selected_token)


# Register alias commands
app.command("apps", hidden=True)(apps_command)
app.command("cloud-accounts", hidden=True)(cloud_accounts_command)
app.command("clouds", hidden=True)(clouds_command)
app.command("clusters", hidden=True)(clusters_command)
app.command("federations", hidden=True)(federations_command)
app.command("networks", hidden=True)(networks_command)
app.command("profiles", hidden=True)(profiles_command)
app.command("teams", hidden=True)(teams_command)


if __name__ == "__main__":
    app()
