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
"""Update cluster command for v8x."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from typing_extensions import Annotated
from vantage_sdk.cluster.application.service_workflow import service_workflow_sdk
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


def _parse_dict_input(
    json_str: Optional[str],
    yaml_path: Optional[Path],
    name: str,
    verbose: bool,
    console,
) -> Dict[str, Any]:
    """Parse dict input from optional JSON string and/or YAML file.

    Args:
        json_str: Optional JSON string to parse
        yaml_path: Optional path to YAML file to load
        name: Input name for error messages (e.g., 'settings', 'config')
        verbose: Whether to print verbose output
        console: Rich console for output

    Returns:
        Merged dict from JSON and YAML inputs (YAML takes precedence)
    """
    result: Dict[str, Any] = {}

    if json_str:
        try:
            result = json.loads(json_str)
            if not isinstance(result, dict):
                raise Abort(
                    f"{name.title()} must be a JSON object (dict), not a {type(result).__name__}.",
                    subject=f"Invalid {name.title()} Format",
                    log_message=f"Invalid {name} format: {type(result).__name__}",
                )
        except json.JSONDecodeError as e:
            raise Abort(
                f"Invalid JSON in --{name}: {e}",
                subject=f"Invalid {name.title()} JSON",
                log_message=f"Failed to parse {name} JSON: {e}",
            )

    if yaml_path:
        try:
            with open(yaml_path) as f:
                file_data = yaml.safe_load(f)
            if file_data:
                if not isinstance(file_data, dict):
                    raise Abort(
                        f"{name.title()} file must contain a YAML mapping (dict), not a {type(file_data).__name__}.",
                        subject=f"Invalid {name.title()} File Format",
                        log_message=f"Invalid {name} file format: {type(file_data).__name__}",
                    )
                # File values take precedence over CLI JSON
                result.update(file_data)
                if verbose:
                    console.print(f"[dim]Loaded {name} from {yaml_path}[/dim]")
        except yaml.YAMLError as e:
            raise Abort(
                f"Invalid YAML in --{name}-file: {e}",
                subject=f"Invalid {name.title()} YAML",
                log_message=f"YAML parse error: {e}",
            )

    return result


async def _merge_and_validate_settings(
    ctx,
    cluster_name: str,
    settings_dict: Dict[str, Any],
    verbose: bool,
    console,
):
    """Fetch existing cluster settings and merge with new values.

    Args:
        ctx: Typer context
        cluster_name: Name of the cluster
        settings_dict: New settings to merge
        verbose: Whether to print verbose output
        console: Rich console for output

    Returns:
        Tuple of (cluster_with_full_settings, merged_settings_dict)
    """
    cluster_with_full_settings = await cluster_sdk.get_cluster_by_name(ctx, cluster_name)
    if cluster_with_full_settings is None:
        raise Abort(
            f"Cluster '{cluster_name}' not found.",
            subject="Cluster Not Found",
            log_message=f"Cluster '{cluster_name}' not found",
        )

    existing_settings = cluster_with_full_settings.creation_parameters.get("settings", {})
    merged_settings = {**existing_settings, **settings_dict}

    if verbose:
        console.print(
            f"[dim]Merged {len(merged_settings)} settings ({len(existing_settings)} existing + new)[/dim]"
        )

    return cluster_with_full_settings, merged_settings


async def _trigger_vdeployer_update(ctx, console, cluster_with_creds, settings_dict):
    """Trigger vdeployer-web to apply updated cluster settings.

    Args:
        ctx: Typer context
        console: Rich console for output
        cluster_with_creds: Cluster object with full credentials
        settings_dict: Complete merged settings to deploy
    """
    console.print("[dim]Triggering vdeployer-web update...[/dim]")

    response = await service_workflow_sdk.trigger_deploy(
        ctx,
        cluster=cluster_with_creds,
        settings=settings_dict,
        target_component="",
    )
    if response.status_code == 200:
        result = response.json() or {}
        console.print(
            f"[green]✓[/green] vdeployer-web update triggered: {result.get('message', 'OK')}"
        )
    elif response.status_code == 409:
        result = response.json() or {}
        console.print(
            f"[yellow]Warning:[/yellow] {result.get('detail', 'A task is already running')}"
        )
    else:
        console.print(
            f"[yellow]Warning:[/yellow] vdeployer-web returned {response.status_code}: {response.text}"
        )


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def update_cluster(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Name of the cluster to update")],
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="New description for the cluster"),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="New status for the cluster"),
    ] = None,
    settings: Annotated[
        Optional[str],
        typer.Option(
            "--settings",
            help='Settings as JSON string (e.g., \'{"key": "value"}\')',
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
    config: Annotated[
        Optional[str],
        typer.Option(
            "--config",
            "-c",
            help='Cluster config as JSON string (e.g., \'{"key": "value"}\').',
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
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            "-m",
            help="Merge new settings with existing settings instead of replacing them",
        ),
    ] = False,
):
    """Update an existing Vantage cluster.

    Update cluster properties such as description, status, settings, or config.
    Only provided fields will be updated; others remain unchanged.

    Examples:
        # Update description
        v8x cluster update my-cluster --description "New description"

        # Update status
        v8x cluster update my-cluster --status ready

        # Replace all settings
        v8x cluster update my-cluster --settings '{"autoscaler_enabled": true}'

        # Merge new settings with existing settings
        v8x cluster update my-cluster --settings '{"new_key": "value"}' --merge

        # Update with settings from YAML file
        v8x cluster update my-cluster --settings-file cluster-settings.yaml

        # Update config
        v8x cluster update my-cluster --config '{"jupyterhub": {"enabled": true}}'

        # Update config from YAML file
        v8x cluster update my-cluster --config-file cluster-config.yaml
    """
    verbose = getattr(ctx.obj, "verbose", False)

    try:
        # Parse settings and config inputs
        settings_dict = _parse_dict_input(
            settings, settings_file, "settings", verbose, ctx.obj.console
        )
        config_dict = _parse_dict_input(config, config_file, "config", verbose, ctx.obj.console)

        # Set merged config as settings.config
        if config_dict:
            settings_dict["config"] = config_dict

        # Determine if we have settings to update
        has_settings_update = bool(settings_dict)
        cluster_with_full_settings = None

        # Check if any update fields were provided
        if description is None and status is None and not has_settings_update:
            raise Abort(
                "No update fields provided. Use --description, --status, --settings, --settings-file, --config, or --config-file.",
                subject="No Updates Specified",
                log_message="No update fields provided",
            )

        # If settings are provided, merge with existing and validate
        if has_settings_update:
            cluster_with_full_settings, settings_dict = await _merge_and_validate_settings(
                ctx, cluster_name, settings_dict, verbose, ctx.obj.console
            )

        # Use SDK to update cluster
        cluster = await cluster_sdk.update_cluster(
            ctx,
            name=cluster_name,
            description=description,
            status=status,
            settings=settings_dict if has_settings_update else None,
        )

        if cluster is None:
            raise Abort(
                f"Cluster '{cluster_name}' not found after update.",
                subject="Cluster Not Found",
                log_message=f"Cluster '{cluster_name}' not found after update",
            )

        # If settings were updated, call vdeployer-web to apply the changes
        if has_settings_update:
            assert cluster_with_full_settings is not None
            await _trigger_vdeployer_update(
                ctx, ctx.obj.console, cluster_with_full_settings, settings_dict
            )

        # Build cluster data for display
        cluster_data = {
            "name": cluster.name,
            "status": cluster.status,
            "client_id": cluster.client_id,
            "description": cluster.description,
            "owner_email": cluster.owner_email,
            "cluster_type": cluster.cluster_type,
            "cloud_account_id": cluster.cloud_account_id,
            "settings": cluster.creation_parameters.get("settings", {}),
            "cluster_type_display": cluster.cluster_type_display,
            "is_ready": cluster.is_ready,
            "jupyterhub_url": cluster.jupyterhub_url,
        }

        # Use formatter to render the updated cluster
        ctx.obj.formatter.render_update(
            data=cluster_data,
            resource_name="Cluster",
            resource_id=cluster_name,
            success_message=f"Cluster '{cluster_name}' has been updated.",
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"An unexpected error occurred while updating cluster '{cluster_name}'.",
            details={"error": str(e)},
        )
