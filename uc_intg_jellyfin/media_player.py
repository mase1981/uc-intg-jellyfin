"""
Media Player entity for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from ucapi import MediaPlayer, StatusCodes
from ucapi.media_player import Attributes, Commands, DeviceClasses, Features, RepeatMode, States
from ucapi.api_definitions import BrowseOptions, BrowseResults, SearchOptions, SearchResults

from uc_intg_jellyfin import browser
from uc_intg_jellyfin.const import FF_RW_SECONDS, PERIODIC_REFRESH_INTERVAL

if TYPE_CHECKING:
    import ucapi
    from uc_intg_jellyfin.device import JellyfinDevice

_LOG = logging.getLogger(__name__)

FEATURES = [
    Features.PLAY_PAUSE,
    Features.STOP,
    Features.NEXT,
    Features.PREVIOUS,
    Features.VOLUME,
    Features.VOLUME_UP_DOWN,
    Features.MUTE_TOGGLE,
    Features.SEEK,
    Features.FAST_FORWARD,
    Features.REWIND,
    Features.MEDIA_TITLE,
    Features.MEDIA_ARTIST,
    Features.MEDIA_ALBUM,
    Features.MEDIA_IMAGE_URL,
    Features.MEDIA_POSITION,
    Features.MEDIA_DURATION,
    Features.REPEAT,
    Features.SHUFFLE,
    Features.PLAY_MEDIA,
    Features.BROWSE_MEDIA,
    Features.SEARCH_MEDIA,
]


class JellyfinMediaPlayer(MediaPlayer):

    def __init__(
        self,
        device_id: str,
        device_name: str,
        jellyfin_device: JellyfinDevice,
        api: ucapi.IntegrationAPI,
        sensors: list | None = None,
    ) -> None:
        self._device_id = device_id
        self._jellyfin_device = jellyfin_device
        self._api = api
        self._sensors = sensors or []

        attributes = {
            Attributes.STATE: States.UNAVAILABLE,
            Attributes.MEDIA_TITLE: "",
            Attributes.MEDIA_ARTIST: "",
            Attributes.MEDIA_ALBUM: "",
            Attributes.MEDIA_IMAGE_URL: "",
            Attributes.MEDIA_POSITION: 0,
            Attributes.MEDIA_DURATION: 0,
            Attributes.VOLUME: 100,
            Attributes.MUTED: False,
            Attributes.REPEAT: RepeatMode.OFF,
            Attributes.SHUFFLE: False,
        }

        super().__init__(
            identifier=device_id,
            name=device_name,
            features=FEATURES,
            attributes=attributes,
            device_class=DeviceClasses.STREAMING_BOX,
            cmd_handler=self._handle_command,
        )

        asyncio.create_task(self._periodic_refresh())

    async def _periodic_refresh(self) -> None:
        await asyncio.sleep(PERIODIC_REFRESH_INTERVAL)
        while True:
            try:
                if self._api and self._api.configured_entities.contains(self.id):
                    await self.push_update()
                await asyncio.sleep(PERIODIC_REFRESH_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOG.error("Periodic refresh error for %s: %s", self._device_id, err)
                await asyncio.sleep(PERIODIC_REFRESH_INTERVAL)

    async def browse(self, options: BrowseOptions) -> BrowseResults | StatusCodes:
        return await browser.browse(self._jellyfin_device, self._device_id, options)

    async def search(self, options: SearchOptions) -> SearchResults | StatusCodes:
        return await browser.search(self._jellyfin_device, self._device_id, options)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        _LOG.info("[%s] Command: %s params=%s", self.id, cmd_id, params)

        try:
            if cmd_id == Commands.PLAY_PAUSE:
                await self._jellyfin_device.play_pause(self._device_id)

            elif cmd_id == Commands.STOP:
                await self._jellyfin_device.stop(self._device_id)

            elif cmd_id == Commands.NEXT:
                await self._jellyfin_device.next_track(self._device_id)

            elif cmd_id == Commands.PREVIOUS:
                await self._jellyfin_device.previous_track(self._device_id)

            elif cmd_id == Commands.VOLUME:
                volume = int(params.get("volume", 50)) if params else 50
                await self._jellyfin_device.set_volume(self._device_id, volume)

            elif cmd_id == Commands.VOLUME_UP:
                await self._jellyfin_device.volume_up(self._device_id)

            elif cmd_id == Commands.VOLUME_DOWN:
                await self._jellyfin_device.volume_down(self._device_id)

            elif cmd_id == Commands.MUTE_TOGGLE:
                await self._jellyfin_device.mute_toggle(self._device_id)

            elif cmd_id == Commands.SEEK:
                if params and "media_position" in params:
                    position = int(params["media_position"])
                    success = await self._jellyfin_device.seek(self._device_id, position)
                    if success:
                        self.attributes[Attributes.MEDIA_POSITION] = position
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            elif cmd_id == Commands.FAST_FORWARD:
                current = self.attributes.get(Attributes.MEDIA_POSITION, 0)
                duration = self.attributes.get(Attributes.MEDIA_DURATION, 0)
                new_pos = min(current + FF_RW_SECONDS, duration) if duration else current + FF_RW_SECONDS
                await self._jellyfin_device.seek(self._device_id, new_pos)

            elif cmd_id == Commands.REWIND:
                current = self.attributes.get(Attributes.MEDIA_POSITION, 0)
                new_pos = max(current - FF_RW_SECONDS, 0)
                await self._jellyfin_device.seek(self._device_id, new_pos)

            elif cmd_id == Commands.REPEAT:
                repeat = params.get("repeat", "OFF") if params else "OFF"
                await self._jellyfin_device.send_command(
                    self._device_id, f"SetRepeatMode {repeat}"
                )

            elif cmd_id == Commands.SHUFFLE:
                shuffle = params.get("shuffle", False) if params else False
                mode = "Shuffled" if shuffle else "Sorted"
                await self._jellyfin_device.send_command(
                    self._device_id, f"SetShuffleQueue {mode}"
                )

            elif cmd_id == Commands.PLAY_MEDIA:
                return await self._handle_play_media(params)

            else:
                _LOG.warning("[%s] Unhandled command: %s", self.id, cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

            await asyncio.sleep(0.5)
            await self.push_update()
            return StatusCodes.OK

        except Exception as err:
            _LOG.error("[%s] Command error: %s", self.id, err, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _handle_play_media(self, params: dict[str, Any] | None) -> StatusCodes:
        if not params:
            return StatusCodes.BAD_REQUEST
        media_id = params.get("media_id", "")
        if not media_id:
            return StatusCodes.BAD_REQUEST

        if media_id.startswith("item_"):
            item_id = media_id[5:]
            success = await self._jellyfin_device.play_item(self._device_id, item_id)
            if success:
                await asyncio.sleep(1)
                await self.push_update()
            return StatusCodes.OK if success else StatusCodes.SERVER_ERROR

        _LOG.warning("[%s] Unknown media_id: %s", self.id, media_id)
        return StatusCodes.BAD_REQUEST

    @staticmethod
    def _make_unique_image_url(base_url: str) -> str:
        if not base_url:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}_t={int(time.time() * 1000)}"

    async def push_update(self) -> None:
        if not self._api or not self._api.configured_entities.contains(self.id):
            return

        device_state = self._jellyfin_device.get_device_state(self._device_id)
        state = device_state.get("state", "idle")

        if state == "playing":
            self.attributes[Attributes.STATE] = States.PLAYING
        elif state == "paused":
            self.attributes[Attributes.STATE] = States.PAUSED
        elif state == "idle":
            self.attributes[Attributes.STATE] = States.ON
        else:
            self.attributes[Attributes.STATE] = States.UNAVAILABLE

        self.attributes[Attributes.MEDIA_TITLE] = device_state.get("media_title", "")
        self.attributes[Attributes.MEDIA_ARTIST] = device_state.get("media_artist", "")
        self.attributes[Attributes.MEDIA_ALBUM] = device_state.get("media_album", "")
        self.attributes[Attributes.MEDIA_POSITION] = device_state.get("media_position", 0)
        self.attributes[Attributes.MEDIA_DURATION] = device_state.get("media_duration", 0)
        self.attributes[Attributes.VOLUME] = device_state.get("volume", 100)
        self.attributes[Attributes.MUTED] = device_state.get("muted", False)
        self.attributes[Attributes.SHUFFLE] = device_state.get("shuffle", False)

        repeat_mode = device_state.get("repeat", "RepeatNone")
        if repeat_mode == "RepeatOne":
            self.attributes[Attributes.REPEAT] = RepeatMode.ONE
        elif repeat_mode == "RepeatAll":
            self.attributes[Attributes.REPEAT] = RepeatMode.ALL
        else:
            self.attributes[Attributes.REPEAT] = RepeatMode.OFF

        image = device_state.get("media_image", "")
        if image:
            self.attributes[Attributes.MEDIA_IMAGE_URL] = self._make_unique_image_url(image)
        else:
            self.attributes[Attributes.MEDIA_IMAGE_URL] = ""

        self._api.configured_entities.update_attributes(self.id, self.attributes)

        sensor_state = {
            "state": state,
            "media_title": device_state.get("media_title", ""),
            "media_artist": device_state.get("media_artist", ""),
        }
        for sensor in self._sensors:
            await sensor.update_state(sensor_state)
