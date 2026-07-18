# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Create NIM deployment."""

import json

import typer
from typing_extensions import Annotated
from vantage_sdk.exceptions import Abort
from vantage_sdk.workbench.nim_deployment import nim_deployment_sdk

from v8x.auth import attach_persona
from v8x.config import attach_settings
from v8x.exceptions import handle_abort
from v8x.vantage_rest_api_client import attach_vantage_rest_client


def _parse_env(env: list[str] | None) -> dict[str, str] | None:
    """Parse repeated -e KEY=VALUE entries into a dict."""
    out: dict[str, str] = {}
    for entry in env or []:
        key, sep, value = entry.partition("=")
        if not sep or not key:
            raise Abort(
                f"--env entries must be KEY=VALUE (got '{entry}').",
                subject="Invalid Env",
            )
        out[key] = value
    return out or None


@handle_abort
@attach_settings
@attach_persona
@attach_vantage_rest_client
async def create_nim(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Deployment name")],
    cluster_name: Annotated[str, typer.Option("--cluster", "-c", help="Cluster name")],
    catalog_id: Annotated[
        str,
        typer.Option("--catalog-id", "-i", help="Catalog id, e.g. meta/llama-3.1-8b-instruct"),
    ],
    version: Annotated[
        str, typer.Option("--version", "-v", help="Approved release tag, e.g. 1.8.6")
    ],
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help="Target namespace (default: your profile ns)"),
    ] = None,
    profile: Annotated[
        str | None, typer.Option("--profile", help="NIM resource profile name")
    ] = None,
    platform: Annotated[
        str,
        typer.Option("--platform", help="Serving platform: standalone, kserve, serverless"),
    ] = "standalone",
    precache: Annotated[
        bool, typer.Option("--precache", help="Pre-pull model engines via a NIMCache")
    ] = False,
    replicas_min: Annotated[
        int, typer.Option("--replicas-min", help="Minimum replicas (0 only for serverless)")
    ] = 1,
    replicas_max: Annotated[
        int, typer.Option("--replicas-max", help="Maximum replicas (> min enables HPA)")
    ] = 1,
    cache_size: Annotated[
        str | None, typer.Option("--cache-size", help="Model cache PVC size, e.g. 50Gi")
    ] = None,
    storage_class: Annotated[
        str | None, typer.Option("--storage-class", help="StorageClass for the cache PVC")
    ] = None,
    ingress: Annotated[
        str,
        typer.Option(
            "--ingress",
            help="Ingress type: public (gateway + JWT), private (cluster-internal "
            "only), metallb (L4 LoadBalancer VIP, no JWT)",
        ),
    ] = "public",
    ingress_auth: Annotated[
        str,
        typer.Option(
            "--ingress-auth",
            help="Public-ingress authorization: user (creator-only), org (any "
            "Vantage JWT), unauthenticated (no JWT check)",
        ),
    ] = "user",
    env: Annotated[
        list[str] | None,
        typer.Option("--env", "-e", help="Extra env var KEY=VALUE (repeatable)"),
    ] = None,
    compute_pool: Annotated[
        str | None,
        typer.Option("--compute-pool", "-p", help="GPU compute pool for the NIM pods"),
    ] = None,
    pin_digest: Annotated[
        bool, typer.Option("--pin-digest", help="Record the resolved image digest")
    ] = False,
):
    r"""Deploy a NIM from the catalog.

    Examples:
        v8x cluster nim create my-llama -c my-cluster \\
            -i meta/llama-3.1-8b-instruct -v 1.8.6 \\
            --compute-pool gpu-pool --ingress public --ingress-auth user
    """
    console = ctx.obj.console
    env_dict = _parse_env(env)

    try:
        console.print(f"[dim]Creating NIM deployment '{name}'...[/dim]")
        response = await nim_deployment_sdk.create(
            ctx,
            cluster_name=cluster_name,
            catalog_id=catalog_id,
            version=version,
            name=name,
            namespace=namespace,
            profile=profile,
            platform=platform,
            precache=precache,
            replicas_min=replicas_min,
            replicas_max=replicas_max,
            cache_size=cache_size,
            storage_class=storage_class,
            ingress_type=ingress,
            ingress_auth=ingress_auth,
            env=env_dict,
            compute_pool=compute_pool,
            pin_digest=pin_digest,
        )

        if response.status_code in (200, 201):
            data = response.json() or {}
            if ctx.obj.json_output:
                print(json.dumps(data, default=str))
            else:
                ing = data.get("ingress", {}) or {}
                console.print(f"[green]✓[/green] NIM deployment '{name}' created")
                console.print(f"  Model:   {data.get('catalog_id', catalog_id)}")
                console.print(f"  Version: {data.get('version', version)}")
                console.print(
                    f"  Ingress: {ing.get('type', ingress)}"
                    f" (auth: {ing.get('auth', ingress_auth)})"
                )
                console.print(f"  URL:     {data.get('url', 'N/A')}")
                console.print(f"  Status:  {data.get('status', 'N/A')}")
        else:
            data = response.json() or {}
            detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
            console.print(f"[red]Error:[/red] {response.status_code}: {detail}")

    except Abort:
        raise
    except Exception as e:
        ctx.obj.formatter.render_error(
            error_message="Failed to create NIM deployment.", details={"error": str(e)}
        )
