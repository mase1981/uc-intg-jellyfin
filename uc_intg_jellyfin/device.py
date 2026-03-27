"""
Jellyfin device wrapper using jellyfin-apiclient-python with ucapi-framework.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from jellyfin_apiclient_python import Jellyfin
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE
from ucapi_framework.device import ExternalClientDevice, DeviceEvents

from uc_intg_jellyfin.config import JellyfinConfig
from uc_intg_jellyfin.const import (
    CONNECT_RETRIES,
    CONNECT_RETRY_DELAY,
    POLL_INTERVAL,
    RECONNECT_DELAY,
    TICKS_PER_SECOND,
    WATCHDOG_INTERVAL,
)

_LOG = logging.getLogger(__name__)

OWN_DEVICE_ID = "jellyfin-integration-ucapi"


class JellyfinDevice(ExternalClientDevice):
    """Wrapper for Jellyfin API using ucapi-framework ExternalClientDevice."""

    def __init__(self, device_config: JellyfinConfig, **kwargs) -> None:
        super().__init__(
            device_config=device_config,
            enable_watchdog=True,
            watchdog_interval=WATCHDOG_INTERVAL,
            reconnect_delay=RECONNECT_DELAY,
            max_reconnect_attempts=0,
            **kwargs,
        )

        self._jellyfin = Jellyfin()
        self._client = self._jellyfin.get_client()
        self._user_id: str = device_config.user_id or ""
        self._server_id: str = device_config.server_id or ""
        self._sessions: dict[str, dict[str, Any]] = {}
        self._poll_task: asyncio.Task | None = None

        _LOG.info("JellyfinDevice initialized: host=%s", device_config.host)

    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str | None:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"Jellyfin-{self._device_config.host}"

    @property
    def config(self) -> JellyfinConfig:
        return self._device_config

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def server_id(self) -> str:
        return self._server_id

    async def create_client(self) -> Any:
        self._client = self._jellyfin.get_client()
        device_name = socket.gethostname()
        self._client.config.app("Jellyfin Integration", "2.0.0", device_name, OWN_DEVICE_ID)
        self._client.config.http("Jellyfin-Integration/2.0.0")
        return self._client

    async def connect_client(self) -> None:
        last_err: Exception | None = None
        host = self._device_config.host

        for attempt in range(CONNECT_RETRIES):
            try:
                self._client.config.data["auth.ssl"] = host.startswith("https")

                connect_result = self._client.auth.connect_to_address(host)
                if CONNECTION_STATE(connect_result["State"]) != CONNECTION_STATE.ServerSignIn:
                    raise ConnectionError(f"Cannot reach server at {host}")

                otp = self._device_config.password if len(self._device_config.password) == 6 else None
                password = self._device_config.password if not otp else ""

                auth_result = self._client.auth.login(
                    host, self._device_config.username, password,
                    **({"otp": otp} if otp else {}),
                )
                if "AccessToken" not in auth_result:
                    raise ConnectionError("Authentication failed - check credentials")

                user_settings = self._client.jellyfin.get_user_settings()
                self._user_id = user_settings["Id"]

                try:
                    server_info = self._client.jellyfin.get_system_info()
                    self._server_id = server_info.get("Id", "")
                    _LOG.info("Connected to Jellyfin: %s", server_info.get("ServerName", "Unknown"))
                except Exception:
                    _LOG.warning("Could not get server info")

                await self._poll_sessions()
                self._start_polling()
                return

            except Exception as err:
                last_err = err
                if attempt < CONNECT_RETRIES - 1:
                    _LOG.warning(
                        "[%s] Connection attempt %d/%d failed: %s, retrying in %ds",
                        self.log_id, attempt + 1, CONNECT_RETRIES, err, CONNECT_RETRY_DELAY,
                    )
                    await asyncio.sleep(CONNECT_RETRY_DELAY)

        _LOG.error("[%s] All connection attempts failed", self.log_id)
        raise last_err  # type: ignore[misc]

    async def disconnect_client(self) -> None:
        self._stop_polling()
        self._sessions.clear()
        try:
            if hasattr(self._client, "stop"):
                self._client.stop()
        except Exception as err:
            _LOG.debug("Error disconnecting: %s", err)

    def check_client_connected(self) -> bool:
        try:
            info = self._client.jellyfin.get_system_info()
            return info is not None
        except Exception:
            return False

    def _start_polling(self) -> None:
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    def _stop_polling(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            self._poll_task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL)
                await self._poll_sessions()
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOG.error("Session poll error: %s", err)
                await asyncio.sleep(POLL_INTERVAL)

    async def _poll_sessions(self) -> None:
        try:
            all_sessions = self._client.jellyfin.sessions()
            if not all_sessions:
                return

            user_sessions = [
                s for s in all_sessions
                if s.get("UserId") == self._user_id
                and s.get("DeviceId") != OWN_DEVICE_ID
            ]

            old_sessions = dict(self._sessions)
            self._sessions.clear()

            for session in user_sessions:
                jf_device_id = session.get("DeviceId", "")
                if not jf_device_id:
                    continue
                self._sessions[jf_device_id] = session

            for jf_device_id in set(list(self._sessions.keys()) + list(old_sessions.keys())):
                dev_cfg = self._device_config.find_by_jellyfin_id(jf_device_id)
                if not dev_cfg:
                    continue

                old_state = self._extract_state(old_sessions.get(jf_device_id))
                new_state = self._extract_state(self._sessions.get(jf_device_id))

                if old_state != new_state:
                    uc_state = self._map_uc_state(new_state)
                    self.events.emit(DeviceEvents.UPDATE, dev_cfg.device_id, {"state": uc_state})

        except Exception as err:
            _LOG.error("Failed to poll sessions: %s", err)

    def _extract_state(self, session: dict[str, Any] | None) -> str:
        if not session:
            return "idle"
        now_playing = session.get("NowPlayingItem")
        if not now_playing:
            return "idle"
        play_state = session.get("PlayState", {})
        if play_state.get("IsPaused", False):
            return "paused"
        return "playing"

    @staticmethod
    def _map_uc_state(state: str) -> str:
        if state == "playing":
            return "PLAYING"
        if state == "paused":
            return "PAUSED"
        return "ON"

    def get_device_state(self, device_id: str) -> dict[str, Any]:
        dev_cfg = self._device_config.get_device(device_id)
        if not dev_cfg:
            return {"state": "idle"}

        session = self._sessions.get(dev_cfg.jellyfin_device_id)
        if not session:
            return {"state": "idle"}

        now_playing = session.get("NowPlayingItem", {})
        play_state = session.get("PlayState", {})

        state = self._extract_state(session)

        result: dict[str, Any] = {
            "state": state,
            "session_id": session.get("Id", ""),
            "media_title": "",
            "media_artist": "",
            "media_album": "",
            "media_image": "",
            "media_position": 0,
            "media_duration": 0,
            "volume": play_state.get("VolumeLevel", 100),
            "muted": play_state.get("IsMuted", False),
            "repeat": play_state.get("RepeatMode", "RepeatNone"),
            "shuffle": play_state.get("ShuffleMode", "Sorted") != "Sorted",
        }

        if now_playing:
            result["media_title"] = now_playing.get("Name", "")

            if now_playing.get("Type") == "Episode":
                series = now_playing.get("SeriesName", "")
                se = ""
                if now_playing.get("ParentIndexNumber") and now_playing.get("IndexNumber"):
                    se = f"S{now_playing['ParentIndexNumber']}E{now_playing['IndexNumber']}"
                result["media_artist"] = f"{series} - {se}" if series and se else series
                result["media_album"] = now_playing.get("SeasonName", "")
            elif now_playing.get("Artists"):
                result["media_artist"] = ", ".join(now_playing["Artists"])
                result["media_album"] = now_playing.get("Album", "")

            result["media_position"] = play_state.get("PositionTicks", 0) // TICKS_PER_SECOND
            if now_playing.get("RunTimeTicks"):
                result["media_duration"] = now_playing["RunTimeTicks"] // TICKS_PER_SECOND

            result["media_image"] = self.get_artwork_url(now_playing) or ""

        return result

    def _get_session_id(self, device_id: str) -> str | None:
        dev_cfg = self._device_config.get_device(device_id)
        if not dev_cfg:
            return None
        session = self._sessions.get(dev_cfg.jellyfin_device_id)
        return session.get("Id") if session else None

    async def play(self, device_id: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_unpause(session_id)
            return True
        except Exception as err:
            _LOG.error("Play failed: %s", err)
            return False

    async def pause(self, device_id: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_pause(session_id)
            return True
        except Exception as err:
            _LOG.error("Pause failed: %s", err)
            return False

    async def play_pause(self, device_id: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_playpause(session_id)
            return True
        except Exception as err:
            _LOG.error("Play/pause failed: %s", err)
            return False

    async def stop(self, device_id: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_stop(session_id)
            return True
        except Exception as err:
            _LOG.error("Stop failed: %s", err)
            return False

    async def next_track(self, device_id: str) -> bool:
        return await self.send_command(device_id, "NextTrack")

    async def previous_track(self, device_id: str) -> bool:
        return await self.send_command(device_id, "PreviousTrack")

    async def seek(self, device_id: str, position_seconds: int) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            position_ticks = position_seconds * TICKS_PER_SECOND
            self._client.jellyfin.remote_seek(session_id, position_ticks)
            return True
        except Exception as err:
            _LOG.error("Seek failed: %s", err)
            return False

    async def set_volume(self, device_id: str, volume: int) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_set_volume(session_id, volume)
            return True
        except Exception as err:
            _LOG.error("Set volume failed: %s", err)
            return False

    async def volume_up(self, device_id: str) -> bool:
        return await self.send_command(device_id, "VolumeUp")

    async def volume_down(self, device_id: str) -> bool:
        return await self.send_command(device_id, "VolumeDown")

    async def mute_toggle(self, device_id: str) -> bool:
        return await self.send_command(device_id, "ToggleMute")

    async def send_command(self, device_id: str, command: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.command(session_id, command)
            return True
        except Exception as err:
            _LOG.error("Command '%s' failed: %s", command, err)
            return False

    async def play_item(self, device_id: str, item_id: str) -> bool:
        session_id = self._get_session_id(device_id)
        if not session_id:
            return False
        try:
            self._client.jellyfin.remote_play_media(session_id, [item_id], "PlayNow")
            return True
        except Exception as err:
            _LOG.error("Play item failed: %s", err)
            return False

    def get_artwork_url(self, item: dict[str, Any], max_width: int = 600) -> str | None:
        try:
            artwork_id = None
            artwork_type = None

            if item.get("Type") == "Episode":
                if item.get("BackdropImageTags"):
                    artwork_id = item["Id"]
                    artwork_type = "Backdrop"
                elif item.get("SeriesId") and item.get("SeriesBackdropImageTags"):
                    artwork_id = item["SeriesId"]
                    artwork_type = "Backdrop"
                elif "Primary" in item.get("ImageTags", {}):
                    artwork_id = item["Id"]
                    artwork_type = "Primary"
                elif item.get("SeriesId") and item.get("SeriesPrimaryImageTag"):
                    artwork_id = item["SeriesId"]
                    artwork_type = "Primary"
                elif item.get("SeasonId"):
                    artwork_id = item["SeasonId"]
                    artwork_type = "Primary"
            else:
                if item.get("BackdropImageTags"):
                    artwork_id = item["Id"]
                    artwork_type = "Backdrop"
                elif "Primary" in item.get("ImageTags", {}):
                    artwork_id = item["Id"]
                    artwork_type = "Primary"

            if artwork_id and artwork_type:
                return str(self._client.jellyfin.artwork(artwork_id, artwork_type, max_width))

        except Exception as err:
            _LOG.error("Artwork URL failed: %s", err)

        return None

    def get_libraries(self) -> list[dict[str, Any]]:
        try:
            url = f"/Users/{self._user_id}/Views"
            result = self._client.jellyfin._get(url)
            if result and isinstance(result, dict):
                return result.get("Items", [])
            if result and isinstance(result, list):
                return result
        except Exception as err:
            _LOG.error("Get libraries failed: %s", err)
        return []

    def get_items(
        self,
        parent_id: str,
        item_type: str | None = None,
        limit: int = 50,
        start_index: int = 0,
        sort_by: str = "SortName",
    ) -> dict[str, Any]:
        try:
            params = {
                "ParentId": parent_id,
                "SortBy": sort_by,
                "SortOrder": "Ascending",
                "Limit": str(limit),
                "StartIndex": str(start_index),
                "Fields": "Overview,PrimaryImageAspectRatio",
                "ImageTypeLimit": "1",
            }
            if item_type:
                params["IncludeItemTypes"] = item_type
                params["Recursive"] = "true"

            url = f"/Users/{self._user_id}/Items"
            result = self._client.jellyfin._get(url, params=params)
            if result and isinstance(result, dict):
                return result
        except Exception as err:
            _LOG.error("Get items failed: %s", err)
        return {"Items": [], "TotalRecordCount": 0}

    def search_items(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            params = {
                "SearchTerm": query,
                "Limit": str(limit),
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series,Episode,Audio,MusicAlbum",
                "Fields": "Overview,PrimaryImageAspectRatio",
            }
            url = f"/Users/{self._user_id}/Items"
            result = self._client.jellyfin._get(url, params=params)
            if result and isinstance(result, dict):
                return result.get("Items", [])
        except Exception as err:
            _LOG.error("Search failed: %s", err)
        return []

    def get_active_sessions(self) -> list[dict[str, Any]]:
        return list(self._sessions.values())
