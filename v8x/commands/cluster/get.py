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
"""Get cluster command for v8x."""

import typer
from typing_extensions import Annotated
from vantage_sdk.cluster.crud import cluster_sdk
from vantage_sdk.exceptions import Abort

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def get_cluster(
    ctx: typer.Context,
    cluster_name: Annotated[str, typer.Argument(help="Name of the cluster to get details for")],
):
    """Get details of a specific Vantage cluster."""
    # Use UniversalOutputFormatter for consistent output

    try:
        # Use SDK to get cluster
        cluster = await cluster_sdk.get_cluster(ctx, cluster_name)

        if not cluster:
            ctx.obj.formatter.render_error(
                error_message=f"No cluster found with name '{cluster_name}'."
            )
            raise Abort(
                f"No cluster found with name '{cluster_name}'.",
                subject="Cluster Not Found",
                log_message=f"Cluster '{cluster_name}' not found",
            )

        # Access Cluster attributes directly to build data dict
        cluster_data = {
            "name": cluster.name,
            "status": cluster.status,
            "client_id": cluster.client_id,
            "client_secret": cluster.client_secret,
            "description": cluster.description,
            "owner_email": cluster.owner_email,
            "cluster_type": cluster.cluster_type,
            "cloud_account_id": cluster.cloud_account_id,
            "creation_parameters": cluster.creation_parameters,
            "settings": cluster.creation_parameters.get("settings", {}),
            "cluster_type_display": cluster.cluster_type_display,
            "is_ready": cluster.is_ready,
            "jupyterhub_url": cluster.jupyterhub_url,
            "jupyterhub_token": cluster.creation_parameters.get("jupyterhub_token", ""),
            "sssd_binder_password": cluster.sssd_binder_password,
        }

        # Use formatter to render the cluster details
        ctx.obj.formatter.render_get(
            data=cluster_data, resource_name="Cluster", resource_id=cluster_name
        )

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message=f"An unexpected error occurred while getting cluster '{cluster_name}'.",
            details={"error": str(e)},
        )
