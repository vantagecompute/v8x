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
"""Pydantic models for slurm-juju --options."""

import re

from pydantic import BaseModel, ConfigDict, field_validator

# Juju controller/model names: lowercase alphanumeric, may contain hyphens,
# must start with a letter or digit (matches juju's own naming rules).
_JUJU_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SlurmJujuOptions(BaseModel):
    """Validated `--options` for a slurm-juju deployment.

    Parsed from `controller=<name>,model=<name>` on `v8x cluster create
    --app slurm-juju`. Both fields are required: slurm-juju does no Juju
    provisioning and assumes the controller and model already exist.
    """

    # protected_namespaces=() because we intentionally use a field named
    # `model` and a `model_target` property (juju's terminology, not pydantic's).
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    controller: str
    model: str

    @field_validator("controller", "model")
    @classmethod
    def _validate_juju_name(cls, value: str) -> str:
        value = value.strip()
        if not _JUJU_NAME_RE.fullmatch(value):
            raise ValueError(
                f"'{value}' is not a valid juju name "
                "(lowercase letters, digits and hyphens; must start with a letter or digit)"
            )
        return value

    @property
    def model_target(self) -> str:
        """The `controller:model` target passed to `juju -m`."""
        return f"{self.controller}:{self.model}"
