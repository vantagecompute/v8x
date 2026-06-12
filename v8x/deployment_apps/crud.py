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
"""Deployment App CRUD SDK for discovering and filtering deployment applications."""

import importlib
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from v8x.constants import V8X_DEV_APPS_DIR
from v8x.deployment_apps.schema import DeploymentApp

logger = logging.getLogger(__name__)


class DeploymentAppSDK:
    """SDK for managing deployment app discovery and filtering."""

    def __init__(self):
        """Initialize the Deployment App SDK and discover available apps."""
        self._app_registry: Dict[str, DeploymentApp] = {}
        self._discover_apps()

    def list(
        self,
        cloud: Optional[str] = None,
        substrate: Optional[str] = None,
    ) -> List[DeploymentApp]:
        """List deployment apps with optional filtering.

        Args:
            cloud: Optional cloud filter (e.g., 'localhost', 'aws')
            substrate: Optional substrate filter (e.g., 'lxd', 'metal', 'k8s')

        Returns:
            List of DeploymentApp instances matching the filters
        """
        apps = list(self._app_registry.values())

        # Filter by cloud if specified
        if cloud:
            apps = [app for app in apps if app.cloud == cloud]
            logger.debug(f"Filtered apps by cloud '{cloud}': {[a.name for a in apps]}")

        # Filter by substrate if specified
        if substrate:
            apps = [app for app in apps if app.substrate == substrate]
            logger.debug(f"Filtered apps by substrate '{substrate}': {[a.name for a in apps]}")

        return apps

    def get(self, name: str, cloud: Optional[str] = None) -> Optional[DeploymentApp]:
        """Get a specific deployment app by name, optionally scoped to a cloud.

        Args:
            name: The app name (e.g., 'slurm-lxd-localhost', 'juju-ext')
            cloud: Optional cloud to scope the lookup (e.g., 'lxd', 'microk8s')

        Returns:
            DeploymentApp instance or None if not found
        """
        if cloud:
            return self._app_registry.get(f"{cloud}/{name}")
        # Fallback: search all entries for a matching app name
        for app in self._app_registry.values():
            if app.name == name:
                return app
        return None

    def get_all_clouds(self) -> List[str]:
        """Get a list of all unique clouds across all apps.

        Returns:
            Sorted list of unique cloud names
        """
        clouds: set[str] = set()
        for app in self._app_registry.values():
            clouds.add(app.cloud)
        return sorted(clouds)

    def get_all_substrates(self) -> List[str]:
        """Get a list of all unique substrates across all apps.

        Returns:
            Sorted list of unique substrate names
        """
        substrates = {app.substrate for app in self._app_registry.values()}
        return sorted(substrates)

    def refresh(self) -> None:
        """Force refresh the app registry by rediscovering apps from the filesystem."""
        self._app_registry.clear()
        self._discover_apps()

    # Private methods for app discovery (integrated from apps/utils.py)

    def _discover_apps(self) -> None:
        """Discover all available deployment apps from the filesystem."""
        package_dir = Path(__file__).parent.parent
        apps_dir = package_dir / "apps"

        # Discover built-in and dev apps
        built_in_apps = []
        if apps_dir.exists():
            built_in_apps.extend(self._discover_builtin_apps(apps_dir))
        dev_apps = self._discover_dev_apps()

        # Combine and process all apps
        all_apps = built_in_apps + dev_apps
        for app_path, is_builtin in all_apps:
            self._process_app(app_path, is_builtin)

        logger.debug(f"Discovered {len(self._app_registry)} deployment apps")

    def _discover_builtin_apps(self, root_dir: Path) -> List[tuple[Path, bool]]:
        """Discover built-in apps from package app directories.

        Looks for apps in:
            v8x/apps/{domain}/{category}/{app_name}/
        """
        built_in_apps = []

        for app_module_path in root_dir.rglob("app.py"):
            if any(part.startswith("__") for part in app_module_path.parts):
                continue
            app_path = app_module_path.parent
            built_in_apps.append((app_path, True))
            logger.debug(f"Found app: {app_path.relative_to(root_dir)}")

        return built_in_apps

    def _discover_dev_apps(self) -> List[tuple[Path, bool]]:
        """Discover dev apps from the dev apps directory."""
        dev_apps = []
        if V8X_DEV_APPS_DIR.exists():
            dev_apps_dir = V8X_DEV_APPS_DIR / "apps"
            if dev_apps_dir.exists():
                # Add dev apps directory to Python path
                dev_apps_parent = str(V8X_DEV_APPS_DIR)
                if dev_apps_parent not in sys.path:
                    sys.path.insert(0, dev_apps_parent)

                # Sort dev apps to load keycloak before full (dependency order)
                app_paths = []
                for app_path in dev_apps_dir.iterdir():
                    if app_path.is_dir() and not (
                        app_path.name.startswith("__") or app_path.name.startswith(".")
                    ):
                        app_module_path = app_path / "app.py"
                        if app_module_path.exists():
                            app_paths.append(app_path)

                # Sort so keycloak comes before full
                app_paths.sort(key=lambda p: (0 if "keycloak" in p.name else 1, p.name))

                for app_path in app_paths:
                    dev_apps.append((app_path, False))  # (path, is_builtin)
        return dev_apps

    def _process_app(self, app_path: Path, is_builtin: bool) -> None:
        """Process a single app and add it to the registry."""
        app_name = app_path.name

        try:
            # Load the app module and check if it has a create function
            app_module = self._load_app_module(app_path, app_name, is_builtin)
            if app_module is None or not hasattr(app_module, "create"):
                return

            constants_module = self._load_constants_module(app_path, app_name, is_builtin)

            # Extract app name, cloud and substrate from constants module
            if constants_module and hasattr(constants_module, "APP_NAME"):
                command_name = constants_module.APP_NAME
            else:
                # Fallback to directory name with underscores replaced by hyphens
                command_name = app_name.replace("_", "-")

            cloud = (
                constants_module.CLOUD
                if constants_module and hasattr(constants_module, "CLOUD")
                else "localhost"
            )
            substrate = (
                constants_module.SUBSTRATE
                if constants_module and hasattr(constants_module, "SUBSTRATE")
                else "unknown"
            )

            # Create DeploymentApp instance with module reference
            deployment_app = DeploymentApp(
                name=command_name,
                cloud=cloud,
                substrate=substrate,
                module=app_module,
            )

            # Add to registry using compound key to avoid collisions
            # (e.g., lxd/juju-ext vs on_prem/slurm-lxd-localhost)
            registry_key = f"{cloud}/{command_name}"
            self._app_registry[registry_key] = deployment_app
            logger.debug(
                f"Registered app '{registry_key}' - cloud: {cloud}, substrate: {substrate}"
            )

        except Exception as e:
            logger.debug(f"Failed to process app {app_name}: {e}")

    def _load_app_module(self, app_path: Path, app_name: str, is_builtin: bool):
        """Load the app module.

        Args:
            app_path: Path to the app directory
            app_name: Name of the app directory
            is_builtin: Whether this is a built-in app

        Returns:
            The loaded module or None if loading failed
        """
        try:
            if is_builtin:
                if "apps" not in app_path.parts:
                    return None

                package_dir = Path(__file__).parent.parent
                module_path = ".".join(app_path.relative_to(package_dir).parts)
                app_module = importlib.import_module(f"v8x.{module_path}.app")

                return app_module
            else:
                # For dev apps, check if app.py exists but don't import yet
                # (can be enhanced later to support dev app imports)
                app_file = app_path / "app.py"
                if app_file.exists():
                    # TODO: Implement dev app loading
                    return None
                return None

        except Exception as e:
            logger.debug(f"Failed to load module for app {app_name}: {e}")
            return None

    def _load_constants_module(self, app_path: Path, app_name: str, is_builtin: bool):
        """Load the app constants module.

        Args:
            app_path: Path to the app directory
            app_name: Name of the app directory
            is_builtin: Whether this is a built-in app

        Returns:
            The loaded module or None if loading failed
        """
        try:
            if is_builtin:
                if "apps" not in app_path.parts:
                    return None

                package_dir = Path(__file__).parent.parent
                module_path = ".".join(app_path.relative_to(package_dir).parts)
                constants_module = importlib.import_module(f"v8x.{module_path}.constants")
            else:
                # External apps - no constants module
                constants_module = None

            return constants_module
        except Exception as e:
            logger.debug(f"Failed to load constants module for app {app_name}: {e}")
            return None
