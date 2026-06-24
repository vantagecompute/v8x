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
"""Rendering functions for SLURM Juju on-prem deployments."""

from textwrap import dedent

from rich.console import Console

from v8x.deployments.schema import Deployment

from .constants import APP_NAME

__all__ = [
    "show_deployment_error",
    "success_create_message",
]


def show_deployment_error(console: Console, model_target: str, error: Exception) -> None:
    """Show deployment error message and juju troubleshooting steps."""
    console.print()
    console.print("❌ [bold red]SLURM Juju deployment failed![/bold red]")

    error_msg = str(error)
    if error_msg and not error_msg.isdigit():
        console.print(f"[red]Error: {error_msg}[/red]")

    console.print()
    console.print("[bold]Troubleshooting Steps:[/bold]")
    console.print(f"• Inspect status: [cyan]juju status -m {model_target}[/cyan]")
    console.print(f"• Tail the logs: [cyan]juju debug-log -m {model_target}[/cyan]")
    console.print("• Confirm the juju CLI: [cyan]juju version[/cyan]")
    console.print(
        f"• Confirm controller/model exist: [cyan]juju models[/cyan] (target [cyan]{model_target}[/cyan])"
    )
    console.print(
        "• The vantage-cluster secret may be half-applied. Before retrying, clear it with "
        f"[cyan]juju remove-secret -m {model_target} vantage-cluster[/cyan] "
        "(or remove the deployment to clean up)."
    )
    console.print()


def success_create_message(deployment: Deployment, controller: str, model: str) -> str:
    """Generate the success message for a SLURM Juju deployment."""
    model_target = f"{controller}:{model}"
    cluster_name = deployment.cluster.name

    return dedent(
        f"""\
        🎉 [bold green]SLURM Juju deployment completed successfully![/bold green]

        [bold]Deployment Summary:[/bold]
        • Deployment name: [cyan]{deployment.name}[/cyan]
        • Cluster name: [cyan]{cluster_name}[/cyan]
        • Deployment ID: [cyan]{deployment.id}[/cyan]
        • Juju controller: [cyan]{controller}[/cyan]
        • Juju model: [cyan]{model}[/cyan]
        • Status: [green]Active[/green]

        [bold]Cluster Access:[/bold]
        • Watch convergence: [cyan]juju status -m {model_target} --watch 5s[/cyan]
        • Check Slurm nodes: [cyan]juju exec -m {model_target} --unit slurmctld/0 -- sinfo[/cyan]
        • SSH to the login node: [cyan]juju ssh -m {model_target} sackd/0[/cyan]

        [bold]Cleanup:[/bold]
        • Remove deployment: [cyan]v8x app deployment {APP_NAME} remove {deployment.id}[/cyan]

        [yellow]Note:[/yellow] Slurm installs from the slurm-factory tarball, so first convergence
        takes a few minutes. The compute node registers once slurmd fetches its configless config.
        """
    )
