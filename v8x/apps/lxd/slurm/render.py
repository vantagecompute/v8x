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
"""Rendering functions for Vantage System on LXD deployments."""

from textwrap import dedent

from v8x.deployments.schema import Deployment

__all__ = []


def success_create_message(deployment: Deployment, vantage_url: str) -> str:
    return dedent(
        f"""\
        🎉 [bold green]Vantage System on LXD deployed successfully![/bold green]

        Access your cluster in the Vantage UI: [cyan]{vantage_url}/compute/clusters/{deployment.cluster.client_id}[/cyan]

        [bold]Deployment Summary:[/bold]
        • Deployment ID: {deployment.id}
        • Cluster: {deployment.cluster.name}
        • Substrate: LXD

        [bold]Useful Commands:[/bold]
        • List LXD containers: lxc list
        • View container info: lxc info <container-name>

        [yellow]Note:[/yellow] The vantage-lxd binary has provisioned your Vantage System.
        """
    )


def success_destroy_message(deployment: Deployment) -> str:
    return dedent(
        """\
        ✅ [bold green]Vantage System on LXD cleanup completed successfully![/bold green]

        [bold]Next Steps:[/bold]
        • The LXD containers have been removed
        • You can create a new deployment with: v8x app vantage-system-lxd create
        """
    )
