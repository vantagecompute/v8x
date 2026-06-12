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
"""VDeployer-Web command module for triggering deployments via the vdeployer-web API."""

from v8x import AsyncTyper

from .deploy import deploy_command
from .destroy import destroy_command
from .status import status_command

vdeployer_web_app = AsyncTyper(
    name="vdeployer-web",
    help="Trigger vdeployer-web operations on a cluster.",
    no_args_is_help=True,
)

vdeployer_web_app.command(name="deploy")(deploy_command)
vdeployer_web_app.command(name="destroy")(destroy_command)
vdeployer_web_app.command(name="status")(status_command)

__all__ = ["vdeployer_web_app"]
