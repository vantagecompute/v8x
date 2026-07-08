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
"""Multipass singlenode image manifest resolution."""

import json
import logging
import re
import urllib.request
from typing import Optional

from .constants import MULTIPASS_MANIFEST_URL

logger = logging.getLogger(__name__)

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")

_cached_manifest: Optional[dict] = None


def _fetch_manifest() -> dict:
    """Fetch and cache the remote manifest.json."""
    global _cached_manifest  # noqa: PLW0603
    if _cached_manifest is not None:
        return _cached_manifest

    try:
        with urllib.request.urlopen(MULTIPASS_MANIFEST_URL, timeout=15) as resp:
            manifest = json.loads(resp.read().decode())
            _cached_manifest = manifest
            return manifest
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch multipass image manifest from {MULTIPASS_MANIFEST_URL}: {exc}"
        ) from exc


def resolve_image_version(version_or_channel: str = "latest") -> str:
    """Resolve a channel name to a concrete version string.

    If *version_or_channel* looks like a full semver (``X.Y.Z``), return it
    as-is.  Otherwise treat it as a channel key (``latest``, ``0.1``, etc.)
    and look it up in the remote manifest.
    """
    if _SEMVER_RE.match(version_or_channel):
        return version_or_channel

    manifest = _fetch_manifest()
    channels = manifest.get("channels", {})
    version = channels.get(version_or_channel)
    if version is None:
        available = ", ".join(sorted(channels)) or "(none)"
        raise ValueError(
            f"Unknown image channel '{version_or_channel}'. Available channels: {available}"
        )
    return version


def reset_cache() -> None:
    """Clear the cached manifest (for testing)."""
    global _cached_manifest  # noqa: PLW0603
    _cached_manifest = None
