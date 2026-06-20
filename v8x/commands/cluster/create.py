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
"""Create new clusters and register them in Vantage."""

import json
import logging
import re
import urllib.parse
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from typing_extensions import Annotated
from vantage_sdk.cloud import cloud_account_sdk
from vantage_sdk.cloud.schema import CloudType
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.cluster.schema import Cluster
from vantage_sdk.exceptions import Abort

from v8x.apps.on_prem.slurm_multipass.constants import (
    APP_NAME as SLURM_MULTIPASS_APP_NAME,
)
from v8x.apps.on_prem.slurm_multipass.constants import (
    SUPPORTED_MULTIPASS_OPERATING_SYSTEMS,
)
from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client

logger = logging.getLogger(__name__)

SLURM_MULTIPASS_OPTION_KEYS = {"operating_system", "cpu", "mem", "disk"}
SLURM_MULTIPASS_OPERATING_SYSTEM_CHOICES = ", ".join(
    SUPPORTED_MULTIPASS_OPERATING_SYSTEMS
)
SLURM_MULTIPASS_OPTIONS_HELP = (
    "Comma-separated slurm-multipass overrides: "
    f"operating_system choices [{SLURM_MULTIPASS_OPERATING_SYSTEM_CHOICES}], "
    "cpu, mem, disk. Example: "
    "operating_system=rockylinux9,cpu=4,mem=8,disk=128G"
)


class ClusterFootprintSize(str, Enum):
    """Deployment footprint choices for cluster creation."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


def _normalize_multipass_size(value: str, option_name: str) -> str:
    """Normalize Multipass memory/disk sizes to a CLI-friendly unit string."""
    normalized = value.strip().lower()
    if re.fullmatch(r"[1-9][0-9]*", normalized):
        return f"{normalized}GB"

    match = re.fullmatch(r"([1-9][0-9]*)([kmgt])b?", normalized)
    if match:
        amount, unit = match.groups()
        return f"{amount}{unit.upper()}B"

    raise Abort(
        f"Invalid {option_name} value '{value}'. Use a positive size like 8, 8G, or 8GB.",
        subject="Invalid Multipass Option",
        log_message=f"Invalid {option_name} option: {value}",
    )


def _parse_slurm_multipass_options(options: Optional[str], app: Optional[str]) -> Dict[str, str]:
    """Parse --options for slurm-multipass deployments."""
    if not options:
        return {}

    if (app or "").lower() != SLURM_MULTIPASS_APP_NAME:
        raise Abort(
            f"--options is only supported with --app {SLURM_MULTIPASS_APP_NAME}.",
            subject="Unsupported Options",
            log_message=f"--options provided for unsupported app: {app}",
        )

    parsed: Dict[str, str] = {}
    for part in options.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise Abort(
                "--options must be a comma-separated list of key=value pairs.",
                subject="Invalid Options Format",
                log_message=f"Invalid options segment: {part}",
            )
        key, value = (item.strip() for item in part.split("=", 1))
        if key not in SLURM_MULTIPASS_OPTION_KEYS:
            raise Abort(
                f"Unsupported --options key '{key}'. Supported keys: operating_system, cpu, mem, disk.",
                subject="Unsupported Options Key",
                log_message=f"Unsupported --options key: {key}",
            )
        if key in parsed:
            raise Abort(
                f"Duplicate --options key '{key}'.",
                subject="Duplicate Options Key",
                log_message=f"Duplicate --options key: {key}",
            )
        if not value:
            raise Abort(
                f"--options key '{key}' must have a value.",
                subject="Invalid Options Value",
                log_message=f"Empty --options value for key: {key}",
            )
        parsed[key] = value

    if "operating_system" in parsed:
        operating_system = parsed["operating_system"].lower()
        if operating_system not in SUPPORTED_MULTIPASS_OPERATING_SYSTEMS:
            raise Abort(
                f"Unsupported operating_system '{parsed['operating_system']}'. Supported values: {SLURM_MULTIPASS_OPERATING_SYSTEM_CHOICES}.",
                subject="Unsupported Operating System",
                log_message=f"Unsupported operating_system option: {parsed['operating_system']}",
            )
        parsed["operating_system"] = operating_system

    if "cpu" in parsed:
        if not re.fullmatch(r"[1-9][0-9]*", parsed["cpu"]):
            raise Abort(
                f"Invalid cpu value '{parsed['cpu']}'. Use a positive integer.",
                subject="Invalid Multipass Option",
                log_message=f"Invalid cpu option: {parsed['cpu']}",
            )

    if "mem" in parsed:
        parsed["mem"] = _normalize_multipass_size(parsed["mem"], "mem")
    if "disk" in parsed:
        parsed["disk"] = _normalize_multipass_size(parsed["disk"], "disk")

    return parsed


def _build_cluster_ui_url(cluster: Cluster, vantage_url: str) -> str:
    """Build the Vantage UI URL for a cluster."""
    cluster_identifier = getattr(cluster, "client_id", None) or cluster.name
    encoded_identifier = urllib.parse.quote(str(cluster_identifier), safe="")
    return f"{vantage_url.rstrip('/')}/compute/clusters/{encoded_identifier}"


def _print_cluster_ui_url(ctx: typer.Context, cluster: Cluster) -> None:
    """Print the Vantage UI URL for a cluster."""
    cluster_url = _build_cluster_ui_url(cluster, ctx.obj.settings.vantage_url)
    ctx.obj.console.print(f"Access your cluster in the Vantage UI: [cyan]{cluster_url}[/cyan]")


class ClusterTypeChoice(str, Enum):
    """Cluster type choices for the CLI."""

    SLURM = "slurm"
    K8S = "k8s"


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_cluster(  # noqa: C901
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Name of the cluster to create")],
    cloud_account_id: Optional[int] = typer.Option(
        None,
        "--cloud-account-id",
        "-a",
        help="ID of the cloud account to use for deployment (from 'v8x cloud account list').",
    ),
    cloud_account_name: Annotated[
        Optional[str],
        typer.Option(
            "--cloud-account",
            help="Name of the cloud account to use for deployment (from 'v8x cloud account list'). Alternative to --cloud-account-id.",
        ),
    ] = None,
    cluster_type: Annotated[
        ClusterTypeChoice,
        typer.Option(
            "--cluster-type",
            "-t",
            help="Type of cluster to create (slurm or k8s).",
            case_sensitive=False,
        ),
    ] = ClusterTypeChoice.SLURM,
    settings: Annotated[
        Optional[str],
        typer.Option(
            "--settings",
            "-s",
            help="Cluster settings as JSON string (e.g., '{\"autoscaler_enabled\":true}').",
        ),
    ] = None,
    config: Annotated[
        Optional[str],
        typer.Option(
            "--config",
            "-c",
            help='Cluster config as JSON string (e.g., \'{"key":"value"}\').',
        ),
    ] = None,
    settings_file: Annotated[
        Optional[Path],
        typer.Option(
            "--settings-file",
            help="Path to a YAML file containing cluster settings. Merged with --settings (file values take precedence).",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    config_file: Annotated[
        Optional[Path],
        typer.Option(
            "--config-file",
            help="Path to a YAML file containing cluster config. Merged with --config (file values take precedence).",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    app: Annotated[
        Optional[str],
        typer.Option(
            "--app",
            help="Deploy an application after cluster creation.",
            case_sensitive=False,
        ),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Resume app deployment on an existing cluster instead of creating a new one.",
        ),
    ] = False,
    footprint: Annotated[
        ClusterFootprintSize,
        typer.Option(
            "--footprint",
            help="Deployment footprint size for resource allocation (small, medium, large).",
            case_sensitive=False,
        ),
    ] = ClusterFootprintSize.SMALL,
    create_team: Annotated[
        bool,
        typer.Option(
            "--create-team",
            help="Create a team named after the cluster with the current user as owner and the cluster as a resource.",
        ),
    ] = False,
    options: Annotated[
        Optional[str],
        typer.Option(
            "--options",
            help=SLURM_MULTIPASS_OPTIONS_HELP,
        ),
    ] = None,
):
    """Create a new Vantage cluster.

    Use --cloud-account-id or --cloud-account to specify a cloud account created with
    'v8x cloud account create'. The cloud account contains the credentials and
    configuration for the cloud provider.

    Examples:
        Create a cluster using a cloud account by ID:
        $ v8x cluster create mycluster --cloud-account-id 16

        Create a cluster using a cloud account by name:
        $ v8x cluster create mycluster --cloud-account my-aws-account

        Create a cluster with custom settings:
        $ v8x cluster create mycluster --cloud-account-id 16 --settings '{"autoscaler_enabled":true}'

        Create a cluster with an app:
        $ v8x cluster create mycluster --cloud-account-id 16 --app slurm-lxd-localhost

        Create a cluster with an app and custom config:
        $ v8x cluster create mycluster --cloud-account-id 16 --app slurm-lxd-localhost --app-config 'jupyterhub_enabled=false'

        Create a cluster with settings from a YAML file:
        $ v8x cluster create mycluster --cloud-account-id 16 --settings-file cluster-settings.yaml

        Create a cluster with config from a YAML file:
        $ v8x cluster create mycluster --cloud-account-id 16 --config-file cluster-config.yaml

        Resume app deployment on an existing cluster:
        $ v8x cluster create mycluster --cloud-account-id 16 --app slurm-lxd-localhost --resume

        Create a Multipass Slurm cluster with resource/image overrides:
        $ v8x cluster create mycluster --cloud-account my-localhost --app slurm-multipass --options operating_system=rockylinux9,cpu=4,mem=8,disk=128G
    """
    # Use UniversalOutputFormatter for consistent output
    verbose = getattr(ctx.obj, "verbose", False)
    ctx.obj.slurm_multipass_options = _parse_slurm_multipass_options(options, app)

    # Parse settings JSON if provided
    vdeployer_settings_dict: Dict[str, Any] = {}
    if settings:
        try:
            vdeployer_settings_dict = json.loads(settings)
            if not isinstance(vdeployer_settings_dict, dict):
                raise Abort(
                    "Settings must be a JSON object (dict), not a list or scalar.",
                    subject="Invalid Settings Format",
                    log_message=f"Invalid settings format: {type(vdeployer_settings_dict).__name__}",
                )
        except json.JSONDecodeError as e:
            raise Abort(
                f"Invalid JSON in --settings: {e}",
                subject="Invalid Settings JSON",
                log_message=f"JSON parse error: {e}",
            )

    # Load and merge settings from YAML file if provided
    if settings_file:
        try:
            with open(settings_file) as f:
                file_settings = yaml.safe_load(f)
            if file_settings:
                if not isinstance(file_settings, dict):
                    raise Abort(
                        "Settings file must contain a YAML mapping (dict), not a list or scalar.",
                        subject="Invalid Settings File Format",
                        log_message=f"Invalid settings file format: {type(file_settings).__name__}",
                    )
                # File values take precedence over CLI --settings
                vdeployer_settings_dict.update(file_settings)
                if verbose:
                    ctx.obj.console.print(f"[dim]Loaded settings from {settings_file}[/dim]")
        except yaml.YAMLError as e:
            raise Abort(
                f"Invalid YAML in --settings-file: {e}",
                subject="Invalid Settings YAML",
                log_message=f"YAML parse error: {e}",
            )

    # Fetch the cloud account from the API
    if cloud_account_id is not None and cloud_account_name is not None:
        raise Abort(
            "Provide only one of --cloud-account-id or --cloud-account, not both.",
            subject="Conflicting Cloud Account Options",
            log_message="Both cloud_account_id and cloud_account_name provided",
        )
    if cloud_account_id is None and cloud_account_name is None:
        raise Abort(
            "A cloud account is required. Provide --cloud-account-id or --cloud-account.\n\n"
            "List available accounts with: v8x cloud account list",
            subject="Missing Cloud Account",
            log_message="Neither cloud_account_id nor cloud_account_name provided",
        )

    if cloud_account_name is not None:
        cloud_account = await cloud_account_sdk.get_by_name(ctx, cloud_account_name)
        if not cloud_account:
            raise Abort(
                f"Cloud account with name '{cloud_account_name}' not found.\n\n"
                "List available accounts with: v8x cloud account list",
                subject="Cloud Account Not Found",
                log_message=f"Cloud account not found by name: {cloud_account_name}",
            )
        cloud_account_id = cloud_account.id
    else:
        assert cloud_account_id is not None
        cloud_account = await cloud_account_sdk.get(ctx, cloud_account_id)
        if not cloud_account:
            raise Abort(
                f"Cloud account with ID '{cloud_account_id}' not found.\n\nList available accounts with: v8x cloud account list",
                subject="Cloud Account Not Found",
                log_message=f"Cloud account not found: {cloud_account_id}",
            )

    if cloud_account_id is None:
        raise Abort(
            "Cloud account did not include an ID.",
            subject="Invalid Cloud Account",
            log_message="Resolved cloud account has no ID",
        )

    # Determine cloud type from account provider
    try:
        cloud_type_enum = CloudType.from_string(cloud_account.provider)
    except ValueError:
        raise Abort(
            f"Unknown cloud provider '{cloud_account.provider}' for cloud account {cloud_account_id}",
            subject="Unknown Cloud Provider",
            log_message=f"Unknown provider: {cloud_account.provider}",
        )

    actual_cloud = cloud_type_enum.value
    cloud_account_attributes = cloud_account.attributes or {}

    # Recover real cloud type from attributes (e.g., microk8s stored as on_prem in backend)
    if "vantage_cloud_type" in cloud_account_attributes:
        actual_cloud = cloud_account_attributes["vantage_cloud_type"]

    # The settings file provider field is the authoritative source for app
    # routing.  The backend may not support all provider types (e.g. microk8s
    # is stored as on_prem or under an lxd account), so the cloud account
    # provider alone is not reliable for choosing the right app module.
    if vdeployer_settings_dict.get("provider"):
        settings_provider = vdeployer_settings_dict["provider"]
        try:
            CloudType.from_string(settings_provider)
            if settings_provider != actual_cloud:
                logger.info(
                    f"Overriding cloud type '{actual_cloud}' with settings provider '{settings_provider}'"
                )
            actual_cloud = settings_provider
        except ValueError:
            pass

    # Store cloud account info in context for downstream use (e.g., app deployment)
    ctx.obj.cloud_account_id = cloud_account_id
    ctx.obj.cloud_account = cloud_account
    ctx.obj.cloud_config_metadata = cloud_account_attributes  # For app deployment
    ctx.obj.footprint = footprint

    if verbose:
        ctx.obj.console.print(
            f"[dim]Using cloud account '{cloud_account.name}' (ID: {cloud_account_id}, provider: {actual_cloud})[/dim]"
        )

    # Parse config JSON if provided and set it as settings.config
    config_dict: Dict[str, Any] = {}
    if config:
        try:
            config_dict = json.loads(config)
            if not isinstance(config_dict, dict):
                raise Abort(
                    "Config must be a JSON object (dict), not a list or scalar.",
                    subject="Invalid Config Format",
                    log_message=f"Invalid config format: {type(config_dict).__name__}",
                )
        except json.JSONDecodeError as e:
            raise Abort(
                f"Invalid JSON in --config: {e}",
                subject="Invalid Config JSON",
                log_message=f"JSON parse error: {e}",
            )

    # Load and merge config from YAML file if provided
    if config_file:
        try:
            with open(config_file) as f:
                file_config = yaml.safe_load(f)
            if file_config:
                if not isinstance(file_config, dict):
                    raise Abort(
                        "Config file must contain a YAML mapping (dict), not a list or scalar.",
                        subject="Invalid Config File Format",
                        log_message=f"Invalid config file format: {type(file_config).__name__}",
                    )
                # File values take precedence over CLI --config
                config_dict.update(file_config)
                if verbose:
                    ctx.obj.console.print(f"[dim]Loaded config from {config_file}[/dim]")
        except yaml.YAMLError as e:
            raise Abort(
                f"Invalid YAML in --config-file: {e}",
                subject="Invalid Config YAML",
                log_message=f"YAML parse error: {e}",
            )

    # Set merged config as settings.config
    if config_dict:
        vdeployer_settings_dict["config"] = config_dict

    try:
        # If --resume is passed, get existing cluster instead of creating a new one
        if resume:
            if verbose:
                ctx.obj.console.print(
                    f"[bold blue]Resuming deployment for existing cluster '{cluster_name}'...[/bold blue]"
                )

            # Fetch existing cluster
            cluster = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
            if not cluster:
                raise Abort(
                    f"Cluster '{cluster_name}' not found. Cannot resume - the cluster must exist first.",
                    subject="Cluster Not Found",
                    log_message=f"Cluster not found for resume: {cluster_name}",
                )

            ctx.obj.console.print(f"[green]✓[/green] Found existing cluster '{cluster_name}'")
        else:
            vdeployer_settings_dict["cluster_footprint"] = footprint.value

            # Pass organization identity to vdeployer for Istio auth policies
            if ctx.obj.persona and ctx.obj.persona.identity_data:
                identity = ctx.obj.persona.identity_data
                vdeployer_settings_dict["keycloak_organization_id"] = identity.org_id
                vdeployer_settings_dict["keycloak_organization_name"] = identity.org_name

            # Set vantage_url from CLI context (applies to all providers)
            vdeployer_settings_dict["vantage_url"] = ctx.obj.settings.vantage_url

            if actual_cloud == "lxd":
                vdeployer_settings_dict["provider"] = "lxd"

                # Cloud-account-specific values (from cloud account attributes, not provider defaults)
                vdeployer_settings_dict["autoscaler_lxd_client_cert_data"] = (
                    cloud_account_attributes["lxd_client_cert"]
                )
                vdeployer_settings_dict["autoscaler_lxd_client_key_data"] = (
                    cloud_account_attributes["lxd_client_key"]
                )
                vdeployer_settings_dict["autoscaler_lxd_host"] = urllib.parse.urlparse(
                    cloud_account_attributes["lxd_server_url"]
                ).hostname

                required_settings = ["lxd_project_name", "autoscaler_lxd_default_network"]
                missing_settings = [
                    key for key in required_settings if not vdeployer_settings_dict.get(key)
                ]
                if missing_settings:
                    raise Abort(
                        "Missing required LXD settings: " + ", ".join(missing_settings),
                        subject="Missing LXD Settings",
                        log_message=f"Missing required LXD settings: {missing_settings}",
                    )

                if "local_registry" in cloud_account_attributes:
                    # Strip http:// or https:// prefix from local_registry
                    local_registry = cloud_account_attributes["local_registry"]
                    local_registry = local_registry.removeprefix("https://").removeprefix(
                        "http://"
                    )
                    vdeployer_settings_dict["local_registry"] = local_registry
                    vdeployer_settings_dict["autoscaler_cloud_init_local_registry"] = (
                        cloud_account_attributes["local_registry"]
                    )

                if "vantage_node_security_binary_url" in cloud_account_attributes:
                    vdeployer_settings_dict["autoscaler_cloud_init_node_security_binary_url"] = (
                        cloud_account_attributes["vantage_node_security_binary_url"]
                    )

                if "dev_mode" in cloud_account_attributes:
                    vdeployer_settings_dict["autoscaler_cloud_init_dev_mode"] = (
                        cloud_account_attributes["dev_mode"]
                    )
                    logger.info(
                        f"Setting autoscaler_cloud_init_dev_mode to {cloud_account_attributes['dev_mode']}"
                    )
                else:
                    logger.info(
                        f"dev_mode not found in cloud_account_attributes, keys: {list(cloud_account_attributes.keys())}"
                    )

            elif actual_cloud == "microk8s":
                vdeployer_settings_dict["provider"] = "microk8s"

            # Create cluster using SDK
            cluster = await cluster_sdk.create_cluster(
                ctx=ctx,
                name=cluster_name,
                cluster_type=cluster_type.value,
                cloud_account_id=cloud_account_id,
                description=f"Cluster {cluster_name} created via CLI",
                settings=vdeployer_settings_dict,
            )

            ctx.obj.console.print(
                f"[green]✓[/green] Cluster '{cluster_name}' created successfully"
            )
            ctx.obj.console.print(cluster.model_dump())

            # Use formatter to render the created cluster
            ctx.obj.formatter.render_create(
                data=cluster.model_dump(),
                resource_name="Cluster",
            )

        # Create a team for the cluster if requested
        if create_team and not resume:
            await _create_team_for_cluster(ctx, cluster)

        # Deploy application if --app option was provided
        if app:
            await deploy_app_to_cluster(ctx, cluster, app, actual_cloud)

        _print_cluster_ui_url(ctx, cluster)

    except Abort:
        # Re-raise Abort exceptions as they contain user-friendly messages
        raise
    except Exception as e:
        raise Abort(
            f"An unexpected error occurred while creating the cluster.\n\nError details: {type(e).__name__}: {e}",
            subject="Unexpected Error",
            log_message=f"Unexpected error: {e}",
        )


async def _create_team_for_cluster(ctx: typer.Context, cluster: Cluster) -> None:
    """Create a team named after the cluster, add the current user as owner, and attach the cluster."""
    from jose import jwt as jose_jwt
    from vantage_sdk.team.crud import team_sdk

    console = ctx.obj.console
    team_name = f"{cluster.name}-admin"

    try:
        result = await team_sdk.create_team(ctx, team_name)
        team_id = result.get("id")
        if not team_id:
            console.print(f"[yellow]⚠[/yellow] Team '{team_name}' created but no ID returned")
            return

        console.print(f"[green]✓[/green] Team '{team_name}' created (id: {team_id})")

        # Add creator as member
        if ctx.obj.persona and ctx.obj.persona.token_set:
            try:
                claims = jose_jwt.get_unverified_claims(ctx.obj.persona.token_set.access_token)
                user_id = claims.get("sub")
                if user_id:
                    await team_sdk.add_user(ctx, team_id, user_id)
                    console.print("[green]✓[/green] Added current user as team member")
            except Exception as e:
                logger.warning(f"Failed to add user to team: {e}")

        # Assign default roles
        try:
            await team_sdk.update_roles(ctx, team_id, ["kubeflow-admin"])
        except Exception as e:
            logger.warning(f"Failed to assign roles to team: {e}")

        # Attach cluster as resource
        await team_sdk.add_resource(ctx, team_id, cluster.client_id)
        console.print(f"[green]✓[/green] Attached cluster '{cluster.name}' to team '{team_name}'")

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to create team for cluster: {e}")
        console.print("[dim]The cluster was created successfully, but team creation failed.[/dim]")


async def deploy_app_to_cluster(
    ctx: typer.Context,
    cluster: Cluster,
    app_name: str,
    cloud_type: str,
):
    """Deploy an application to the newly created cluster.

    Args:
        ctx: Typer context (cloud_config_metadata available via ctx.obj.cloud_config_metadata)
        cluster: The created cluster
        app_name: Name of the app to deploy
        cloud_type: The actual cloud type (e.g., 'lxd', 'on_prem')
    """
    try:
        # Import SDK here to avoid module-level initialization
        from v8x.deployment_apps import deployment_app_sdk

        logger.info(f"Looking up deployment app '{app_name}' for cloud '{cloud_type}'")

        # Look up app scoped to the cloud type so we get the right implementation
        # (e.g., lxd/juju-ext vs on_prem/slurm-lxd-localhost)
        app = deployment_app_sdk.get(app_name, cloud=cloud_type)

        if app is None and cloud_type == "on_prem":
            # Older local Slurm apps were registered under localhost before moving to
            # the on-prem app tree.
            for fallback_cloud in ("localhost", "lxd"):
                app = deployment_app_sdk.get(app_name, cloud=fallback_cloud)
                if app is not None:
                    logger.warning(
                        f"No '{cloud_type}/{app_name}' app found; resolved via "
                        f"'{fallback_cloud}/{app_name}'. Consider recreating the cloud "
                        f"account with the latest CLI to set vantage_cloud_type."
                    )
                    break

        if app is None and cloud_type not in ("on_prem",):
            # Only fall back to unscoped lookup for non-ambiguous cloud types
            logger.warning(f"No '{cloud_type}/{app_name}' app found; trying unscoped lookup")
            app = deployment_app_sdk.get(app_name)

        if app is None:
            available_apps_list = deployment_app_sdk.list()
            available_apps = ", ".join(a.name for a in available_apps_list)
            raise Abort(
                f"App '{app_name}' not found. Available apps: {available_apps}",
                subject="App Not Found",
                log_message=f"App not found for cluster deploy: {app_name}",
            )

        logger.info(
            f"[bold blue]Deploying app '{app_name}' to cluster '{cluster.name}'...[/bold blue]"
        )

        # Check if app has a module with create function
        if app.module and hasattr(app.module, "create"):
            create_function = getattr(app.module, "create")

            # Call the create function
            logger.info(f"[dim]Calling {app.name}.create()...[/dim]")
            result = await create_function(ctx, cluster)

            # Check if the function returned an error exit code
            if isinstance(result, typer.Exit) and result.exit_code != 0:
                raise Abort(
                    f"App '{app_name}' deployment failed with exit code {result.exit_code}.",
                    subject="App Deployment Failed",
                    log_message=f"App deployment failed: {app_name} exit={result.exit_code}",
                )
            elif isinstance(result, typer.Exit) and result.exit_code == 0:
                logger.info(f"[bold green]✓ App '{app_name}' deployed successfully![/bold green]")
            else:
                # No exit code returned, assume success
                logger.info(f"[bold green]✓ App '{app_name}' deployment completed![/bold green]")
        else:
            raise Abort(
                f"App '{app_name}' does not support automatic deployment.",
                subject="Unsupported App Deployment",
                log_message=f"App does not support automatic deployment: {app_name}",
            )

    except Abort:
        raise
    except Exception as e:
        import traceback

        logger.error(f"[bold red]✗ Failed to deploy app '{app_name}':[/bold red]")
        logger.error(f"[red]{type(e).__name__}: {e}[/red]")
        if getattr(ctx.obj, "verbose", False):
            logger.error(f"[dim]{traceback.format_exc()}[/dim]")
        raise Abort(
            f"Failed to deploy app '{app_name}'. Error details: {type(e).__name__}: {e}",
            subject="App Deployment Failed",
            log_message=f"Failed to deploy app {app_name}: {e}",
        ) from e
