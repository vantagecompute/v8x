# Copyright (C) 2025 Vantage Compute Corporation
# GPL-3.0 — see LICENSE.
"""Ray job (KubeRay) commands."""

from v8x import AsyncTyper

from .clusters import clusters_ray
from .create import create_ray_job
from .delete import delete_ray_job
from .get import get_ray_job
from .list import list_ray_jobs

ray_app = AsyncTyper(
    name="ray",
    help="Manage Ray jobs and clusters (KubeRay) on a cluster.",
    invoke_without_command=True,
    no_args_is_help=True,
)

ray_app.command("create")(create_ray_job)
ray_app.command("list")(list_ray_jobs)
ray_app.command("get")(get_ray_job)
ray_app.command("delete")(delete_ray_job)
ray_app.command("clusters")(clusters_ray)
