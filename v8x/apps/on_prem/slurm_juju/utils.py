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
"""Juju CLI helpers for slurm-juju on-prem deployments.

This module shells out to the ``juju`` binary exclusively — slurm-juju does not
use the in-tree WebSocket client (``v8x.libjuju``). Every command targets an
existing controller + model via ``-m <controller>:<model>``; slurm-juju performs
no Juju provisioning (no add-model / bootstrap / destroy-model).
"""

import logging
import os
import shutil
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Dict, List

import snick
import yaml
from vantage_sdk.exceptions import Abort

from .constants import (
    JUJU_DEFAULT_TIMEOUT,
    JUJU_DEPLOY_TIMEOUT,
    SSSD_APP_NAME,
    SSSD_LDAP_URI_OPTION,
)

logger = logging.getLogger(__name__)

JUJU_BINARY = "juju"

# key=value option keys whose values must never be written to logs/console.
# The v8x file log handler is always DEBUG, so secret-bearing argv (juju
# add-secret) would otherwise persist in cleartext to ~/.v8x/debug.log.
SENSITIVE_OPTION_KEYS = frozenset({"client-secret", "ldap-bind-password", "client-id"})


def _redact_for_log(args: List[str]) -> List[str]:
    """Mask the values of sensitive ``key=value`` argv items for logging."""
    redacted: List[str] = []
    for arg in args:
        key, sep, _value = arg.partition("=")
        if sep and key in SENSITIVE_OPTION_KEYS:
            redacted.append(f"{key}=***")
        else:
            redacted.append(arg)
    return redacted


def check_juju_available() -> None:
    """Ensure the ``juju`` CLI is installed, aborting with install help if not.

    Raises:
        Abort: If the juju binary is not found on PATH.
    """
    if not shutil.which(JUJU_BINARY):
        message = snick.dedent(
            """
            • Juju not found. Please install Juju first.

            • To install Juju, run the following command:
              sudo snap install juju

            • Or visit https://juju.is/docs/juju/install-juju for other installation methods.
            """
        ).strip()

        raise Abort(
            message,
            subject="Juju Required",
            log_message="Juju binary not found",
        )


def derive_ldap_uri(ldap_url: str, port: int) -> str:
    """Build the sssd ldap-uri from the settings-derived openldap URL.

    ``settings.get_ldap_url()`` already maps ``vantage_url`` to the openldap
    host (replacing the first FQDN label with ``openldap``), e.g.
    ``https://app.dev.vantagecompute.ai`` -> ``ldaps://openldap.dev.vantagecompute.ai``.
    We only append the LDAPS port here.
    """
    return f"{ldap_url}:{port}"


def render_bundle(ldap_uri: str) -> str:
    """Render the vendored Topology-A bundle with the derived ldap-uri injected.

    The bundle ships verbatim from vantage-slurm-charm-operators (charms resolved
    from Charmhub ``edge``); the only override is the ``sssd`` application's
    ``ldap-uri``, derived from the active profile's ``vantage_url``.

    Returns:
        The rendered bundle YAML as a string, ready to write to a temp file.
    """
    raw = resources.files(__package__).joinpath("bundle.yaml").read_text()
    data = yaml.safe_load(raw)

    sssd_options = data["applications"][SSSD_APP_NAME].setdefault("options", {})
    sssd_options[SSSD_LDAP_URI_OPTION] = ldap_uri

    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def write_bundle_tempfile(bundle_yaml: str) -> str:
    """Write the rendered bundle to a juju-readable temp file; return its path.

    The juju CLI is strictly confined (installed as a snap): it cannot read the
    host's ``/tmp`` (the snap has a private /tmp namespace) nor hidden dot-dirs
    under ``$HOME`` (the snap ``home`` interface excludes dotfiles). So we write
    the bundle into a NON-hidden temp directory under ``$HOME``, which the snap
    can read. The caller must remove the returned file's parent directory
    (see ``bundle_tempdir``) when done.
    """
    bundle_dir = tempfile.mkdtemp(prefix="v8x-slurm-juju-", dir=str(Path.home()))
    bundle_path = os.path.join(bundle_dir, "bundle.yaml")
    with open(bundle_path, "w") as handle:
        handle.write(bundle_yaml)
    return bundle_path


def bundle_tempdir(bundle_path: str) -> str:
    """Return the temp directory that holds a path from ``write_bundle_tempfile``."""
    return os.path.dirname(bundle_path)


def bundle_application_names() -> List[str]:
    """Return every application name defined in the vendored bundle.

    Used by ``remove`` to tear down the deployed apps (leaving the model intact).
    """
    raw = resources.files(__package__).joinpath("bundle.yaml").read_text()
    data = yaml.safe_load(raw)
    return list(data.get("applications", {}).keys())


def _run_juju(
    args: List[str],
    *,
    timeout: int = JUJU_DEFAULT_TIMEOUT,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run ``juju <args>`` and return the completed process.

    Args:
        args: Arguments after the ``juju`` executable (never includes ``juju``).
        timeout: Seconds before the call is aborted.
        check: When True, raise RuntimeError on a non-zero exit.

    Raises:
        RuntimeError: If juju is missing, times out, or (when check) exits non-zero.
    """
    cmd = [JUJU_BINARY, *args]
    logger.debug("Running: %s", " ".join([JUJU_BINARY, *_redact_for_log(args)]))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError("juju CLI not found in PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"juju {args[0]} timed out after {timeout}s") from exc

    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip() or "no error output"
        raise RuntimeError(f"`juju {args[0]}` failed (exit {result.returncode}): {stderr}")

    return result


def juju_deploy(model_target: str, bundle_path: str) -> None:
    """Deploy a bundle file into an existing model (``juju deploy -m <target>``)."""
    _run_juju(
        ["deploy", "-m", model_target, bundle_path],
        timeout=JUJU_DEPLOY_TIMEOUT,
    )


def juju_add_secret(model_target: str, name: str, data: Dict[str, str]) -> str:
    """Create a Juju secret and return its ``secret:...`` URI.

    Values are passed as discrete ``key=value`` argv items (no shell), so secret
    values are not interpolated by a shell.
    """
    kv_args = [f"{key}={value}" for key, value in data.items()]
    result = _run_juju(["add-secret", "-m", model_target, name, *kv_args])
    secret_id = (result.stdout or "").strip()
    if not secret_id:
        raise RuntimeError(f"`juju add-secret {name}` returned no secret URI")
    return secret_id


def juju_grant_secret(model_target: str, secret_id: str, application: str) -> None:
    """Grant a secret to an application (``juju grant-secret``)."""
    _run_juju(["grant-secret", "-m", model_target, secret_id, application])


def juju_config(model_target: str, application: str, key: str, value: str) -> None:
    """Set a single application config value (``juju config``)."""
    _run_juju(["config", "-m", model_target, application, f"{key}={value}"])


def juju_remove_application(model_target: str, application: str) -> None:
    """Remove a single application, forcing through errored units."""
    _run_juju(
        ["remove-application", "-m", model_target, application, "--force", "--no-prompt"],
    )


def juju_remove_secret(model_target: str, name: str) -> None:
    """Remove a secret by name/URI (``juju remove-secret``)."""
    _run_juju(["remove-secret", "-m", model_target, name])
