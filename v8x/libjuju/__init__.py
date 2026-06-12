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
"""Minimal Juju WebSocket API client.

This module provides a lightweight wrapper around the Juju WebSocket API,
implementing only the functionality needed for the v8x. It replaces
the heavier pylibjuju dependency.

The implementation communicates directly with the Juju controller via its
WebSocket-based JSON-RPC API.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets
import yaml

logger = logging.getLogger(__name__)


class JujuError(Exception):
    """Base exception for Juju-related errors."""

    pass


class JujuConnectionError(JujuError):
    """Raised when connection to Juju controller fails."""

    pass


class JujuAPIError(JujuError):
    """Raised when Juju API returns an error response."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Juju Data File Helpers
# ---------------------------------------------------------------------------


def _get_juju_data_path() -> Path:
    """Get the Juju data directory path.

    Returns:
        Path to Juju data directory (~/.local/share/juju)
    """
    juju_data = os.environ.get("JUJU_DATA")
    if juju_data:
        return Path(juju_data)
    return Path.home() / ".local" / "share" / "juju"


def _load_juju_controllers() -> dict[str, Any]:
    """Load Juju controllers configuration.

    Returns:
        Dictionary containing controllers configuration
    """
    controllers_path = _get_juju_data_path() / "controllers.yaml"
    if not controllers_path.exists():
        raise JujuError(f"Juju controllers file not found: {controllers_path}")
    with open(controllers_path) as f:
        return yaml.safe_load(f) or {}


def _load_juju_accounts() -> dict[str, Any]:
    """Load Juju accounts configuration.

    Returns:
        Dictionary containing accounts configuration
    """
    accounts_path = _get_juju_data_path() / "accounts.yaml"
    if not accounts_path.exists():
        return {}
    with open(accounts_path) as f:
        return yaml.safe_load(f) or {}


def _get_current_controller() -> str | None:
    """Get the name of the current/default controller.

    Returns:
        Name of current controller or None
    """
    controllers = _load_juju_controllers()
    return controllers.get("current-controller")


def _get_controller_info(controller_name: str | None = None) -> dict[str, Any]:
    """Get controller connection information.

    Args:
        controller_name: Name of controller, or None for current

    Returns:
        Dictionary with endpoint, ca_cert, and user info
    """
    controllers_data = _load_juju_controllers()
    accounts_data = _load_juju_accounts()

    if controller_name is None:
        controller_name = controllers_data.get("current-controller")
    if not controller_name:
        raise JujuError("No controller specified and no current controller set")

    controllers = controllers_data.get("controllers", {})
    if controller_name not in controllers:
        raise JujuError(f"Controller '{controller_name}' not found")

    controller = controllers[controller_name]
    api_endpoints = controller.get("api-endpoints", [])
    if not api_endpoints:
        raise JujuError(f"No API endpoints found for controller '{controller_name}'")

    # Get account info
    accounts = accounts_data.get("controllers", {})
    account = accounts.get(controller_name, {})

    return {
        "endpoints": api_endpoints,
        "ca_cert": controller.get("ca-cert"),
        "username": account.get("user"),
        "password": account.get("password"),
        "controller_uuid": controller.get("uuid"),
    }


# ---------------------------------------------------------------------------
# WebSocket RPC Connection
# ---------------------------------------------------------------------------


@dataclass
class Connection:
    """WebSocket connection to Juju controller or model."""

    endpoint: str
    ca_cert: str | None
    username: str | None
    password: str | None
    uuid: str | None = None  # Model UUID (None for controller connection)
    _ws: Any = field(default=None, repr=False)
    _request_id: int = field(default=0, repr=False)
    _facades: dict[str, int] = field(default_factory=dict, repr=False)
    _receiver_task: Any = field(default=None, repr=False)
    _pending: dict[int, asyncio.Future] = field(default_factory=dict, repr=False)

    @classmethod
    async def connect(
        cls,
        endpoint: str,
        ca_cert: str | None = None,
        username: str | None = None,
        password: str | None = None,
        uuid: str | None = None,
    ) -> "Connection":
        """Connect to a Juju API endpoint.

        Args:
            endpoint: API endpoint (host:port)
            ca_cert: CA certificate for TLS
            username: Username for authentication
            password: Password for authentication
            uuid: Model UUID (None for controller-only connection)

        Returns:
            Connected Connection instance
        """
        conn = cls(
            endpoint=endpoint,
            ca_cert=ca_cert,
            username=username,
            password=password,
            uuid=uuid,
        )
        await conn._connect_and_login()
        return conn

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for websocket connection."""
        ssl_context = ssl.create_default_context()
        if self.ca_cert:
            # Write CA cert to temp file for ssl context
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(self.ca_cert)
                ca_path = f.name
            try:
                ssl_context.load_verify_locations(ca_path)
            finally:
                os.unlink(ca_path)
        else:
            # Disable verification if no CA cert (not recommended for production)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def _connect_and_login(self) -> None:
        """Establish websocket connection and authenticate."""
        # Build URL
        if self.uuid:
            url = f"wss://{self.endpoint}/model/{self.uuid}/api"
        else:
            url = f"wss://{self.endpoint}/api"

        ssl_context = self._get_ssl_context()

        self._ws = await websockets.connect(
            url,
            ssl=ssl_context,
            max_size=2**22,  # 4MB max frame size
        )

        # Start receiver task
        self._receiver_task = asyncio.create_task(self._receiver())

        # Login
        await self._login()

    async def _receiver(self) -> None:
        """Background task to receive messages and dispatch to pending requests."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    request_id = data.get("request-id")
                    if request_id and request_id in self._pending:
                        future = self._pending.pop(request_id)
                        if not future.done():
                            future.set_result(data)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from Juju API")
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Receiver error: {e}")

    async def _login(self) -> None:
        """Authenticate with the Juju controller."""
        params: dict[str, Any] = {
            "auth-tag": f"user-{self.username}" if self.username else "",
        }
        if self.password:
            params["credentials"] = self.password

        result = await self._rpc_raw("Admin", "Login", 3, params)
        response = result.get("response", {})

        # Build facade version map
        facades = response.get("facades", [])
        for facade in facades:
            name = facade.get("name")
            versions = facade.get("versions", [])
            if name and versions:
                self._facades[name] = max(versions)

    async def _rpc_raw(
        self, facade_type: str, request: str, version: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send raw RPC request to Juju API.

        Args:
            facade_type: Name of the facade (e.g., "Admin", "ModelManager")
            request: Method name (e.g., "Login", "CreateModel")
            version: Facade version
            params: Request parameters

        Returns:
            Response dictionary
        """
        self._request_id += 1
        request_id = self._request_id

        msg = {
            "type": facade_type,
            "request": request,
            "version": version,
            "request-id": request_id,
            "params": params,
        }

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            await self._ws.send(json.dumps(msg))
            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise JujuConnectionError("Request timed out")

        # Check for errors
        if "error" in result:
            error = result["error"]
            raise JujuAPIError(error, code=result.get("error-code"))

        return result

    async def rpc(
        self, facade_type: str, request: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send RPC request using negotiated facade version.

        Args:
            facade_type: Name of the facade
            request: Method name
            params: Request parameters

        Returns:
            Response dictionary
        """
        version = self._facades.get(facade_type, 1)
        return await self._rpc_raw(facade_type, request, version, params or {})

    async def close(self) -> None:
        """Close the websocket connection."""
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None


# ---------------------------------------------------------------------------
# Status classes for representing Juju model status
# ---------------------------------------------------------------------------


@dataclass
class StatusInfo:
    """Represents status information for a unit/application."""

    status: str
    message: str = ""
    since: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StatusInfo | None":
        """Create StatusInfo from dict."""
        if data is None:
            return None
        return cls(
            status=data.get("status", "unknown"),
            message=data.get("message", ""),
            since=data.get("since", ""),
        )


@dataclass
class UnitStatus:
    """Represents the status of a Juju unit."""

    workload_status: StatusInfo | None
    agent_status: StatusInfo | None
    machine: str = ""
    leader: bool = False
    public_address: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnitStatus":
        """Create UnitStatus from dict."""
        return cls(
            workload_status=StatusInfo.from_dict(data.get("workload-status")),
            agent_status=StatusInfo.from_dict(data.get("agent-status")),
            machine=data.get("machine", ""),
            leader=data.get("leader", False),
            public_address=data.get("public-address", ""),
        )


@dataclass
class ApplicationStatus:
    """Represents the status of a Juju application."""

    status: StatusInfo | None
    charm: str = ""
    exposed: bool = False
    units: dict[str, UnitStatus] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationStatus":
        """Create ApplicationStatus from dict."""
        units_data = data.get("units", {})
        units = {name: UnitStatus.from_dict(unit_data) for name, unit_data in units_data.items()}
        return cls(
            status=StatusInfo.from_dict(data.get("status")),
            charm=data.get("charm", ""),
            exposed=data.get("exposed", False),
            units=units,
        )


@dataclass
class FullStatus:
    """Represents the full status of a Juju model."""

    model: dict[str, Any]
    applications: dict[str, ApplicationStatus]
    machines: dict[str, Any]
    relations: list[Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FullStatus":
        """Create FullStatus from dict."""
        apps_data = data.get("applications", {})
        applications = {
            name: ApplicationStatus.from_dict(app_data) for name, app_data in apps_data.items()
        }
        return cls(
            model=data.get("model", {}),
            applications=applications,
            machines=data.get("machines", {}),
            relations=data.get("relations", []),
        )


# ---------------------------------------------------------------------------
# Action class for tracking action execution
# ---------------------------------------------------------------------------


@dataclass
class Action:
    """Represents a Juju action execution."""

    id: str
    status: str
    results: dict[str, Any] = field(default_factory=dict)
    _model: Any = field(default=None, repr=False)

    async def wait(self, timeout: float = 300.0) -> "Action":
        """Wait for the action to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Self with updated status and results
        """
        if self._model is None:
            return self

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                result = await self._model._connection.rpc(
                    "Action",
                    "Actions",
                    {"entities": [{"tag": f"action-{self.id}"}]},
                )
                results = result.get("response", {}).get("results", [])
                if results:
                    action_result = results[0]
                    self.status = action_result.get("status", self.status)
                    self.results = action_result.get("output", {})

                    if self.status in ("completed", "failed", "aborted"):
                        return self
            except JujuAPIError:
                pass

            await asyncio.sleep(1)

        return self


# ---------------------------------------------------------------------------
# Unit class
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """Represents a Juju unit."""

    name: str
    _model: Any = field(default=None, repr=False)

    @property
    def tag(self) -> str:
        """Get the unit tag."""
        return f"unit-{self.name.replace('/', '-')}"

    async def run_action(self, action_name: str, **params: Any) -> Action:
        """Run an action on this unit.

        Args:
            action_name: Name of the action to run
            **params: Action parameters

        Returns:
            Action instance that can be awaited
        """
        if self._model is None:
            raise JujuError("Unit not connected to a model")

        result = await self._model._connection.rpc(
            "Action",
            "EnqueueOperation",
            {
                "actions": [
                    {
                        "name": action_name,
                        "parameters": params,
                        "receiver": self.tag,
                    }
                ]
            },
        )

        actions = result.get("response", {}).get("actions", [])
        if not actions:
            raise JujuAPIError("No action was enqueued")

        action_info = actions[0]
        action_tag = action_info.get("action", {}).get("tag", "")
        action_id = action_tag.replace("action-", "") if action_tag else ""

        return Action(id=action_id, status="pending", _model=self._model)

    async def run(self, command: str, timeout: int | None = None) -> Action:
        """Run a command on this unit.

        Args:
            command: Shell command to run
            timeout: Optional timeout in seconds

        Returns:
            Action instance with results
        """
        if self._model is None:
            raise JujuError("Unit not connected to a model")

        params: dict[str, Any] = {
            "applications": [],
            "commands": command,
            "machines": [],
            "units": [self.name],
        }
        if timeout:
            params["timeout"] = timeout * 1_000_000_000  # Convert to nanoseconds

        result = await self._model._connection.rpc("Action", "Run", params)

        actions = result.get("response", {}).get("actions", [])
        if not actions:
            raise JujuAPIError("No action was returned")

        action_info = actions[0]
        action = action_info.get("action", {})
        action_tag = action.get("tag", "")
        action_id = action_tag.replace("action-", "") if action_tag else ""

        action_obj = Action(id=action_id, status="pending", _model=self._model)
        return await action_obj.wait()

    async def is_leader_from_status(self) -> bool:
        """Check if this unit is the leader.

        Returns:
            True if this unit is the leader, False otherwise
        """
        if self._model is None:
            return False

        try:
            status = await self._model.get_status()
            app_name = self.name.split("/")[0]
            app_status = status.get("applications", {}).get(app_name, {})
            units = app_status.get("units", {})
            unit_status = units.get(self.name, {})
            return unit_status.get("leader", False)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Application class
# ---------------------------------------------------------------------------


@dataclass
class Application:
    """Represents a Juju application."""

    name: str
    _model: Any = field(default=None, repr=False)
    _status: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def units(self) -> list[Unit]:
        """Get list of units for this application."""
        unit_list = []
        units_data = self._status.get("units", {})
        for unit_name in units_data:
            unit_list.append(Unit(name=unit_name, _model=self._model))
        return unit_list

    async def set_config(self, config: dict[str, str]) -> None:
        """Set configuration options for this application.

        Args:
            config: Dictionary of config key-value pairs
        """
        if self._model is None:
            raise JujuError("Application not connected to a model")

        await self._model._connection.rpc(
            "Application",
            "SetConfigs",
            {
                "Args": [
                    {
                        "application": self.name,
                        "config": config,
                    }
                ]
            },
        )


# ---------------------------------------------------------------------------
# Model class
# ---------------------------------------------------------------------------


class Model:
    """Represents a Juju model."""

    def __init__(
        self,
        name: str,
        uuid: str,
        connection: Connection | None = None,
    ):
        self.name = name
        self.uuid = uuid
        self._connection = connection
        self._applications: dict[str, Application] = {}

    @property
    def applications(self) -> dict[str, Application]:
        """Get dictionary of applications in this model."""
        return self._applications

    async def deploy(
        self,
        bundle_path_or_charm: str,
        *,
        application_name: str | None = None,
        channel: str | None = None,
        num_units: int | None = None,
        base: str | None = None,
    ) -> None:
        """Deploy a bundle or charm to this model.

        Args:
            bundle_path_or_charm: Path to a bundle file or a charm name
            application_name: Optional application name when deploying a charm
            channel: Optional charm channel
            num_units: Optional number of units for a charm deploy
            base: Optional Juju base for a charm deploy
        """
        if self._connection is None:
            raise JujuError("Model not connected")

        bundle_file = Path(bundle_path_or_charm)
        if not bundle_file.exists():
            import subprocess

            cmd = ["juju", "deploy", bundle_path_or_charm, "--model", self.name]
            if application_name:
                cmd.append(application_name)
            if channel:
                cmd.extend(["--channel", channel])
            if num_units is not None:
                cmd.extend(["--num-units", str(num_units)])
            if base:
                cmd.extend(["--base", base])

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except FileNotFoundError as exc:
                raise JujuError("juju CLI not found - required for charm deployment") from exc
            except subprocess.TimeoutExpired as exc:
                raise JujuError("Charm deploy timed out") from exc

            if result.returncode != 0:
                raise JujuError(f"Charm deploy failed: {result.stderr}")
            return

        with open(bundle_file) as f:
            bundle_yaml = f.read()

        # Get bundle changes from the Bundle facade
        result = await self._connection.rpc(
            "Bundle",
            "GetChanges",
            {"bundleURL": "", "yaml": bundle_yaml},
        )

        changes = result.get("response", {}).get("changes", [])
        errors = result.get("response", {}).get("errors", [])
        if errors:
            raise JujuAPIError(f"Bundle errors: {errors}")

        # Execute the bundle changes
        # This is a simplified implementation - full implementation would
        # need to handle charm deployment, relations, etc.
        await self._execute_bundle_changes(changes, bundle_yaml)

    async def integrate(self, endpoint_a: str, endpoint_b: str) -> None:
        """Integrate two application endpoints using the Juju CLI."""
        import subprocess

        try:
            result = subprocess.run(
                ["juju", "integrate", "--model", self.name, endpoint_a, endpoint_b],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise JujuError("juju CLI not found - required for integration") from exc
        except subprocess.TimeoutExpired as exc:
            raise JujuError("Charm integration timed out") from exc

        if result.returncode != 0:
            raise JujuError(f"Charm integration failed: {result.stderr}")

    async def _execute_bundle_changes(
        self, changes: list[dict[str, Any]], bundle_yaml: str
    ) -> None:
        """Execute bundle changes.

        For complex bundles, we use juju CLI as a fallback since the API
        for full bundle deployment is complex (charm resolution, resources, etc.)
        """
        import subprocess

        # Use juju CLI for bundle deployment as it handles all the complexity
        try:
            result = subprocess.run(
                ["juju", "deploy", "--model", self.name, "-"],
                input=bundle_yaml,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise JujuError(f"Bundle deploy failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise JujuError("Bundle deploy timed out")
        except FileNotFoundError:
            raise JujuError("juju CLI not found - required for bundle deployment")

    async def get_status(self, filters: list[str] | None = None) -> FullStatus:
        """Get full status of the model.

        Args:
            filters: Optional list of application/unit patterns to filter

        Returns:
            FullStatus object containing model status
        """
        if self._connection is None:
            raise JujuError("Model not connected")

        params: dict[str, Any] = {}
        if filters:
            params["patterns"] = filters

        result = await self._connection.rpc("Client", "FullStatus", params)
        status_data = result.get("response", {})

        # Update applications cache
        apps_status = status_data.get("applications", {})
        for app_name, app_data in apps_status.items():
            if app_name not in self._applications:
                self._applications[app_name] = Application(
                    name=app_name, _model=self, _status=app_data
                )
            else:
                self._applications[app_name]._status = app_data

        return FullStatus.from_dict(status_data)

    async def add_secret(
        self, name: str, data_args: list[str], file: str = "", info: str = ""
    ) -> str:
        """Add a secret to this model.

        Args:
            name: Name/label for the secret
            data_args: List of key=value pairs for secret data
            file: Optional path to YAML file with secret data
            info: Optional description of the secret

        Returns:
            Secret URI (e.g., "secret:xxxxx")
        """
        if self._connection is None:
            raise JujuError("Model not connected")

        # Parse data args into dict and base64 encode values
        data = {}
        for arg in data_args:
            if "=" not in arg:
                continue
            key, value = arg.split("=", 1)
            # Values need to be base64 encoded
            data[key] = base64.b64encode(value.encode()).decode()

        result = await self._connection.rpc(
            "Secrets",
            "CreateSecrets",
            {
                "args": [
                    {
                        "content": {"data": data},
                        "description": info,
                        "label": name,
                    }
                ]
            },
        )

        results = result.get("response", {}).get("results", [])
        if not results:
            raise JujuAPIError("No result from CreateSecrets")

        secret_result = results[0]
        if secret_result.get("error"):
            raise JujuAPIError(str(secret_result["error"]))

        return secret_result.get("result", "")

    async def grant_secret(self, secret_name: str, *applications: str) -> None:
        """Grant access to a secret to specified applications.

        Args:
            secret_name: Name/label of the secret
            *applications: Names of applications to grant access to
        """
        if self._connection is None:
            raise JujuError("Model not connected")

        await self._connection.rpc(
            "Secrets",
            "GrantSecret",
            {
                "applications": list(applications),
                "label": secret_name,
            },
        )

    async def disconnect(self) -> None:
        """Disconnect from the model."""
        if self._connection:
            await self._connection.close()
            self._connection = None


# ---------------------------------------------------------------------------
# Controller class
# ---------------------------------------------------------------------------


class Controller:
    """Juju controller client."""

    def __init__(self):
        self._connection: Connection | None = None
        self._controller_name: str | None = None

    async def connect(self, controller_name: str | None = None) -> None:
        """Connect to a Juju controller.

        Args:
            controller_name: Name of controller (or None for current)
        """
        self._controller_name = controller_name

        info = _get_controller_info(controller_name)

        # Try each endpoint until one works
        last_error = None
        for endpoint in info["endpoints"]:
            try:
                self._connection = await Connection.connect(
                    endpoint=endpoint,
                    ca_cert=info.get("ca_cert"),
                    username=info.get("username"),
                    password=info.get("password"),
                    uuid=None,  # Controller-level connection
                )
                return
            except Exception as e:
                last_error = e
                continue

        raise JujuConnectionError(f"Failed to connect to any endpoint: {last_error}")

    async def disconnect(self) -> None:
        """Disconnect from the controller."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def add_model(
        self,
        model_name: str,
        cloud_name: str | None = None,
        region: str | None = None,
    ) -> Model:
        """Create a new model.

        Args:
            model_name: Name for the new model
            cloud_name: Optional cloud to host the model
            region: Optional region within the cloud

        Returns:
            Model instance for the new model
        """
        if self._connection is None:
            raise JujuError("Not connected to controller")

        # Get controller info for owner tag
        info = _get_controller_info(self._controller_name)
        username = info.get("username", "admin")

        params: dict[str, Any] = {
            "name": model_name,
            "owner-tag": f"user-{username}",
        }
        if cloud_name:
            params["cloud-tag"] = f"cloud-{cloud_name}"
        if region:
            params["region"] = region

        result = await self._connection.rpc("ModelManager", "CreateModel", params)
        model_info = result.get("response", {})
        model_uuid = model_info.get("uuid")

        if not model_uuid:
            raise JujuAPIError("Failed to create model - no UUID returned")

        # Connect to the new model
        model_connection = await Connection.connect(
            endpoint=self._connection.endpoint,
            ca_cert=self._connection.ca_cert,
            username=self._connection.username,
            password=self._connection.password,
            uuid=model_uuid,
        )

        return Model(name=model_name, uuid=model_uuid, connection=model_connection)

    async def get_model(self, model_name: str) -> Model:
        """Get an existing model by name.

        Args:
            model_name: Name of the model

        Returns:
            Model instance
        """
        if self._connection is None:
            raise JujuError("Not connected to controller")

        # List models to find UUID
        result = await self._connection.rpc("ModelManager", "ListModels", {})
        models = result.get("response", {}).get("user-models", [])

        model_uuid = None
        for model_info in models:
            model = model_info.get("model", {})
            if model.get("name") == model_name:
                model_uuid = model.get("uuid")
                break

        if not model_uuid:
            raise JujuError(f"Model '{model_name}' not found")

        # Connect to the model
        model_connection = await Connection.connect(
            endpoint=self._connection.endpoint,
            ca_cert=self._connection.ca_cert,
            username=self._connection.username,
            password=self._connection.password,
            uuid=model_uuid,
        )

        return Model(name=model_name, uuid=model_uuid, connection=model_connection)

    async def destroy_model(
        self,
        model_name: str,
        destroy_storage: bool = False,
        force: bool = False,
        max_wait: int | None = None,
    ) -> None:
        """Destroy a model.

        Args:
            model_name: Name of the model to destroy
            destroy_storage: Whether to destroy storage
            force: Force destruction even if model has errors
            max_wait: Maximum time to wait in seconds
        """
        if self._connection is None:
            raise JujuError("Not connected to controller")

        # Get model UUID first
        result = await self._connection.rpc("ModelManager", "ListModels", {})
        models = result.get("response", {}).get("user-models", [])

        model_uuid = None
        for model_info in models:
            model = model_info.get("model", {})
            if model.get("name") == model_name:
                model_uuid = model.get("uuid")
                break

        if not model_uuid:
            raise JujuError(f"Model '{model_name}' not found")

        # Destroy the model
        params: dict[str, Any] = {
            "models": [
                {
                    "model-tag": f"model-{model_uuid}",
                    "destroy-storage": destroy_storage,
                    "force": force,
                }
            ]
        }
        if max_wait is not None:
            params["models"][0]["max-wait"] = max_wait

        await self._connection.rpc("ModelManager", "DestroyModels", params)


# Export public API
__all__ = [
    "Controller",
    "Model",
    "Application",
    "Unit",
    "Action",
    "Connection",
    "FullStatus",
    "ApplicationStatus",
    "UnitStatus",
    "StatusInfo",
    "JujuError",
    "JujuConnectionError",
    "JujuAPIError",
]
