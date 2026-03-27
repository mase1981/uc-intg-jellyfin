"""
Setup flow for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
import socket
from typing import Any

from jellyfin_apiclient_python import Jellyfin
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE
from ucapi import RequestUserInput, SetupAction
from ucapi_framework import BaseSetupFlow

from uc_intg_jellyfin.config import JellyfinConfig

_LOG = logging.getLogger(__name__)


class JellyfinSetupFlow(BaseSetupFlow[JellyfinConfig]):

    async def get_pre_discovery_screen(self) -> RequestUserInput | None:
        return self.get_manual_entry_form()

    async def _handle_discovery(self) -> SetupAction:
        if self._pre_discovery_data:
            host = self._pre_discovery_data.get("host")
            username = self._pre_discovery_data.get("username")
            password = self._pre_discovery_data.get("password")

            if not all([host, username, password]):
                return self.get_manual_entry_form()

            try:
                result = await self.query_device(self._pre_discovery_data)
                if hasattr(result, "identifier"):
                    return await self._finalize_device_setup(result, self._pre_discovery_data)
                return result
            except Exception as err:
                _LOG.error("Discovery failed: %s", err)
                return self.get_manual_entry_form()

        return await self._handle_manual_entry()

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Jellyfin Server Setup"},
            [
                {
                    "id": "host",
                    "label": {"en": "Server URL"},
                    "field": {
                        "text": {
                            "placeholder": "http://192.168.1.100:8096",
                        }
                    },
                },
                {
                    "id": "username",
                    "label": {"en": "Username"},
                    "field": {"text": {"placeholder": "your_username"}},
                },
                {
                    "id": "password",
                    "label": {"en": "Password"},
                    "field": {"password": {}},
                },
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> JellyfinConfig | RequestUserInput:
        host = (input_values.get("host") or "").strip().rstrip("/")
        username = (input_values.get("username") or "").strip()
        password = (input_values.get("password") or "").strip()

        if not all([host, username, password]):
            return self.get_manual_entry_form()

        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"

        _LOG.info("Validating connection to %s...", host)

        jellyfin = Jellyfin()
        client = jellyfin.get_client()

        try:
            device_name = socket.gethostname()
            client.config.app("Jellyfin Integration", "2.0.0", device_name, "jellyfin-setup-ucapi")
            client.config.http("Jellyfin-Integration/2.0.0")
            client.config.data["auth.ssl"] = host.startswith("https")

            connect_result = client.auth.connect_to_address(host)
            if CONNECTION_STATE(connect_result["State"]) != CONNECTION_STATE.ServerSignIn:
                raise ValueError(f"Cannot reach Jellyfin server at {host}")

            auth_result = client.auth.login(host, username, password)
            if "AccessToken" not in auth_result:
                raise ValueError("Authentication failed - check credentials")

            user_settings = client.jellyfin.get_user_settings()
            user_id = user_settings["Id"]

            server_info = {}
            try:
                server_info = client.jellyfin.get_system_info()
            except Exception:
                _LOG.warning("Could not get server info during setup")

            server_id = server_info.get("Id", "unknown")
            server_name = server_info.get("ServerName", "Jellyfin")

            config_id = f"jellyfin_{server_id[:12]}".lower()

            config = JellyfinConfig(
                identifier=config_id,
                name=f"Jellyfin ({server_name})",
                host=host,
                username=username,
                password=password,
                user_id=user_id,
                server_id=server_id,
            )

            try:
                all_sessions = client.jellyfin.sessions()
                user_sessions = [
                    s for s in (all_sessions or [])
                    if s.get("UserId") == user_id
                    and s.get("DeviceId") != "jellyfin-setup-ucapi"
                ]

                for session in user_sessions:
                    jf_device_id = session.get("DeviceId", "")
                    if not jf_device_id:
                        continue
                    client_name = session.get("Client", "Unknown")
                    device_name_s = session.get("DeviceName", "")
                    if device_name_s and device_name_s != client_name:
                        name = f"{client_name} ({device_name_s})"
                    else:
                        name = client_name
                    config.add_device(jf_device_id, name)

                _LOG.info("Discovered %d device(s)", len(config.devices))
            except Exception as err:
                _LOG.warning("Session discovery failed: %s", err)

            return config

        except Exception as err:
            _LOG.error("Setup validation failed: %s", err)
            raise ValueError(f"Setup failed: {err}") from err

        finally:
            try:
                if hasattr(client, "stop"):
                    client.stop()
            except Exception:
                pass
