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
"""SLURM Juju on-prem application support.

Deploys the vantage-slurm-charm-operators Topology-A bundle into an existing
Juju model (selected via ``--options controller=<name>,model=<name>``) and wires
the one required ``vantage-cluster`` secret. slurm-juju does no Juju provisioning:
the controller and model are assumed to exist.
"""

import logging
import os
import shutil

import typer
from typing_extensions import Annotated
from vantage_sdk.cloud.crud import cloud_sdk
from vantage_sdk.cluster.schema import Cluster, VantageClusterContext

from v8x.config import attach_settings
from v8x.deployment_apps.common import (
    create_deployment_with_init_status,
    generate_dev_cluster_data,
)
from v8x.deployments.crud import deployment_sdk
from v8x.deployments.schema import Deployment
from v8x.exceptions import handle_abort

from .constants import (
    APP_NAME,
    CLOUD,
    CLUSTER_SECRET_CONSUMERS,
    CLUSTER_SECRET_NAME,
    LDAP_PORT,
    META_JUJU_CONTROLLER,
    META_JUJU_MODEL,
    SUBSTRATE,
)
from .render import show_deployment_error, success_create_message
from .schema import SlurmJujuOptions
from .utils import (
    bundle_application_names,
    check_juju_available,
    derive_ldap_uri,
    juju_add_secret,
    juju_config,
    juju_deploy,
    juju_grant_secret,
    juju_remove_application,
    juju_remove_secret,
    render_bundle,
    write_bundle_tempfile,
)

logger = logging.getLogger(__name__)

VANTAGE_SECRET_CONFIG_KEY = "vantage-secret"


def _create_cluster_secret(
    model_target: str,
    *,
    vantage_url: str,
    client_id: str,
    client_secret: str,
    org_id: str,
    ldap_bind_password: str,
) -> str:
    """Create + grant the shared vantage-cluster secret and set it on both charms.

    Mirrors deployment.md section 3: one secret, granted to vantage-agent and
    sssd, with ``vantage-secret=<SID>`` configured on each.

    Returns:
        The ``secret:...`` URI of the created secret.
    """
    secret_data = {
        "vantage-url": vantage_url,
        "client-id": client_id,
        "client-secret": client_secret,
        "org-id": org_id,
        "ldap-bind-password": ldap_bind_password,
    }
    secret_id = juju_add_secret(model_target, CLUSTER_SECRET_NAME, secret_data)

    for application in CLUSTER_SECRET_CONSUMERS:
        juju_grant_secret(model_target, secret_id, application)
        juju_config(model_target, application, VANTAGE_SECRET_CONFIG_KEY, secret_id)

    return secret_id


async def create(ctx: typer.Context, cluster: Cluster) -> typer.Exit:
    """Deploy the SLURM Juju bundle and wire the vantage-cluster secret.

    Args:
        ctx: Typer context carrying console/verbose/settings/persona and the
            parsed ``slurm_juju_options``.
        cluster: Cluster object with OIDC + SSSD credentials.

    Returns:
        typer.Exit with code 0 on success, 1 on failure.
    """
    console = ctx.obj.console
    verbose = ctx.obj.verbose
    settings = ctx.obj.settings
    org_id = ctx.obj.persona.identity_data.org_id

    check_juju_available()

    options: SlurmJujuOptions | None = getattr(ctx.obj, "slurm_juju_options", None)
    if options is None:
        console.print(
            "[bold red]Error:[/bold red] slurm-juju requires "
            "--options controller=<controller-name>,model=<model-name>"
        )
        return typer.Exit(code=1)

    controller = options.controller
    model = options.model
    model_target = options.model_target

    client_secret = cluster.client_secret
    sssd_binder_password = cluster.sssd_binder_password

    if sssd_binder_password is None:
        console.print(
            "[bold red]Error:[/bold red] Cluster is missing SSSD binder password. Please debug"
        )
        return typer.Exit(code=1)

    if client_secret is None:
        console.print("[bold red]Error:[/bold red] Cluster is missing client secret. Please debug")
        return typer.Exit(code=1)

    if not org_id:
        console.print(
            "[bold red]Error:[/bold red] Persona is missing org_id; cannot configure SSSD. "
            "Please debug"
        )
        return typer.Exit(code=1)

    jupyterhub_token = (cluster.creation_parameters or {}).get("jupyterhub_token")
    if jupyterhub_token is None:
        console.print(
            "[bold red]Error:[/bold red] Cluster is missing jupyterhub_token in "
            "creation_parameters. Please debug"
        )
        return typer.Exit(code=1)

    vantage_cluster_ctx = VantageClusterContext(
        cluster_name=cluster.name,
        client_id=cluster.client_id,
        client_secret=client_secret,
        base_api_url=settings.get_apis_url(),
        oidc_base_url=settings.get_auth_url(),
        oidc_domain=settings.oidc_domain,
        tunnel_api_url=settings.get_tunnel_url(),
        jupyterhub_token=jupyterhub_token,
        sssd_binder_password=sssd_binder_password,
        ldap_url=settings.get_ldap_url(),
        org_id=org_id,
    )

    cloud = cloud_sdk.get(CLOUD)
    if cloud is None:
        logger.debug("Cloud '%s' not found. Please debug", CLOUD)
        raise typer.Exit(code=1)

    deployment = create_deployment_with_init_status(
        app_name=APP_NAME,
        cluster=cluster,
        vantage_cluster_ctx=vantage_cluster_ctx,
        verbose=verbose,
        cloud=cloud,
        substrate=SUBSTRATE,
        additional_metadata={
            META_JUJU_CONTROLLER: controller,
            META_JUJU_MODEL: model,
        },
    )

    ldap_uri = derive_ldap_uri(settings.get_ldap_url(), LDAP_PORT)
    bundle_yaml = render_bundle(ldap_uri=ldap_uri)

    bundle_path: str | None = None
    try:
        # NOTE: written under a non-hidden $HOME dir (not /tmp) because the juju
        # snap is confined and cannot read the host /tmp or hidden dot-dirs.
        bundle_path = write_bundle_tempfile(bundle_yaml)

        console.print(
            f"⚙️  Deploying the Charmed HPC bundle to controller "
            f"[cyan]{controller}[/cyan], model [cyan]{model}[/cyan] "
            "(this can take a few minutes)..."
        )
        juju_deploy(model_target, bundle_path)

        console.print(
            "[green]✓[/green] Bundle deployed. Configuring the vantage-cluster secret..."
        )
        _create_cluster_secret(
            model_target,
            vantage_url=settings.vantage_url,
            client_id=cluster.client_id,
            client_secret=client_secret,
            org_id=org_id,
            ldap_bind_password=sssd_binder_password,
        )
    except Exception as e:
        deployment.status = "error"
        deployment.write()
        show_deployment_error(console, model_target, e)
        return typer.Exit(code=1)
    finally:
        if bundle_path is not None:
            shutil.rmtree(os.path.dirname(bundle_path), ignore_errors=True)

    deployment.status = "active"
    deployment.write()

    console.print(
        success_create_message(
            deployment=deployment,
            controller=controller,
            model=model,
        )
    )
    return typer.Exit(0)


@handle_abort
@attach_settings
async def create_command(
    ctx: typer.Context,
    cluster_name: Annotated[
        str,
        typer.Argument(help="Name of the cluster to create"),
    ],
    controller: Annotated[
        str,
        typer.Option("--controller", help="Existing Juju controller to deploy into"),
    ],
    model: Annotated[
        str,
        typer.Option("--model", help="Existing Juju model to deploy into"),
    ],
    dev_run: Annotated[
        bool, typer.Option("--dev-run", help="Use dummy cluster data for local development")
    ] = False,
) -> None | typer.Exit:
    """Create a Vantage SLURM cluster on an existing Juju controller + model."""
    ctx.obj.slurm_juju_options = SlurmJujuOptions(controller=controller, model=model)

    deploy_to_cluster: Cluster | None = generate_dev_cluster_data(cluster_name)

    if not dev_run:
        from vantage_sdk.cluster.crud import cluster_sdk

        if (cluster := await cluster_sdk.get_cluster_by_name(ctx, cluster_name)) is not None:
            deploy_to_cluster = cluster
        else:
            raise typer.Exit(code=1)

    await create(ctx=ctx, cluster=deploy_to_cluster)


async def remove(ctx: typer.Context, deployment: Deployment) -> None:
    """Remove a SLURM Juju deployment's applications (the model is left intact).

    Args:
        ctx: The typer context object for console access.
        deployment: The deployment object to remove.
    """
    await _remove_deployment(deployment=deployment)


@handle_abort
@attach_settings
async def remove_command(
    ctx: typer.Context,
    deployment_id: Annotated[
        str,
        typer.Argument(help="ID of the deployment to remove"),
    ],
) -> None:
    """Remove a Vantage SLURM Juju deployment by its deployment ID."""
    deployment = await deployment_sdk.get_deployment(ctx, deployment_id)
    if deployment is not None:
        await remove(ctx=ctx, deployment=deployment)
        await deployment_sdk.delete(deployment.id)
        ctx.obj.console.print(
            f"[green]✓[/green] Deployment '{deployment.name}' removed successfully"
        )
        return

    ctx.obj.console.print(f"[bold red]Error:[/bold red] Deployment '{deployment_id}' not found.")
    return


async def _remove_deployment(deployment: Deployment) -> None:
    """Remove the bundle's applications from the deployment's controller + model.

    Best-effort per application: failures are logged and removal continues so a
    single stuck app does not block teardown of the rest.

    Raises:
        RuntimeError: If the deployment lacks recorded juju controller/model.
    """
    check_juju_available()

    metadata = deployment.additional_metadata or {}
    controller = metadata.get(META_JUJU_CONTROLLER)
    model = metadata.get(META_JUJU_MODEL)
    if not controller or not model:
        raise RuntimeError(
            "Deployment is missing juju controller/model metadata; cannot remove applications"
        )

    model_target = f"{controller}:{model}"
    for application in bundle_application_names():
        try:
            juju_remove_application(model_target, application)
        except RuntimeError as e:
            logger.warning("Failed to remove application %s: %s", application, e)

    # Remove the post-deploy secret too, so a later re-deploy into the same
    # model does not fail on `juju add-secret` (the name is non-idempotent).
    try:
        juju_remove_secret(model_target, CLUSTER_SECRET_NAME)
    except RuntimeError as e:
        logger.warning("Failed to remove secret %s: %s", CLUSTER_SECRET_NAME, e)
