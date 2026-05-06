"""
Media Player entity for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from ucapi import StatusCodes, media_player
from ucapi.media_player import (
    Attributes,
    BrowseOptions,
    BrowseResults,
    Commands,
    DeviceClasses,
    Features,
    MediaContentType,
    RepeatMode,
    SearchOptions,
    SearchResults,
    States,
)
from ucapi_framework import create_entity_id, MediaPlayerEntity

from uc_intg_jellyfin import browser
from uc_intg_jellyfin.const import FF_RW_SECONDS

if TYPE_CHECKING:
    from uc_intg_jellyfin.config import JellyfinDeviceConfig
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
    Features.MEDIA_TYPE,
    Features.MEDIA_POSITION,
    Features.MEDIA_DURATION,
    Features.REPEAT,
    Features.SHUFFLE,
    Features.PLAY_MEDIA,
    Features.BROWSE_MEDIA,
    Features.SEARCH_MEDIA,
]

_JELLYFIN_TYPE_TO_CONTENT_TYPE = {
    "Movie": MediaContentType.MOVIE,
    "Episode": MediaContentType.EPISODE,
    "Audio": MediaContentType.MUSIC,
    "MusicVideo": MediaContentType.VIDEO,
    "Video": MediaContentType.VIDEO,
    "TvChannel": MediaContentType.CHANNEL,
}


class JellyfinMediaPlayer(MediaPlayerEntity):

    def __init__(
        self,
        device_config: JellyfinDeviceConfig,
        device: JellyfinDevice,
    ) -> None:
        self._device = device
        self._device_id = device_config.device_id
        self._sensors: list = []
        self._last_media_item_id: str = ""

        entity_id = create_entity_id(
            media_player.EntityTypes.MEDIA_PLAYER, device_config.device_id
        )

        super().__init__(
            entity_id,
            device_config.name,
            FEATURES,
            {
                Attributes.STATE: States.UNKNOWN,
                Attributes.MEDIA_TITLE: "",
                Attributes.MEDIA_ARTIST: "",
                Attributes.MEDIA_ALBUM: "",
                Attributes.MEDIA_IMAGE_URL: "",
                Attributes.MEDIA_TYPE: "",
                Attributes.MEDIA_POSITION: 0,
                Attributes.MEDIA_DURATION: 0,
                Attributes.VOLUME: 100,
                Attributes.MUTED: False,
                Attributes.REPEAT: RepeatMode.OFF,
                Attributes.SHUFFLE: False,
            },
            device_class=DeviceClasses.STREAMING_BOX,
            cmd_handler=self._handle_command,
        )

        self.subscribe_to_device(device)

    def set_sensors(self, sensors: list) -> None:
        self._sensors = sensors

    async def sync_state(self) -> None:
        if not self._device.is_connected:
            self.update({Attributes.STATE: States.UNAVAILABLE})
            return

        device_state = self._device.get_device_state(self._device_id)
        state_str = device_state.get("state", "idle")

        attrs: dict[str, Any] = {}

        if state_str == "playing":
            attrs[Attributes.STATE] = States.PLAYING
        elif state_str == "paused":
            attrs[Attributes.STATE] = States.PAUSED
        elif state_str == "idle":
            attrs[Attributes.STATE] = States.ON
        else:
            attrs[Attributes.STATE] = States.UNAVAILABLE

        attrs[Attributes.MEDIA_TITLE] = device_state.get("media_title", "")
        attrs[Attributes.MEDIA_ARTIST] = device_state.get("media_artist", "")
        attrs[Attributes.MEDIA_ALBUM] = device_state.get("media_album", "")
        attrs[Attributes.MEDIA_POSITION] = device_state.get("media_position", 0)
        attrs[Attributes.MEDIA_DURATION] = device_state.get("media_duration", 0)
        attrs[Attributes.VOLUME] = device_state.get("volume", 100)
        attrs[Attributes.MUTED] = device_state.get("muted", False)
        attrs[Attributes.SHUFFLE] = device_state.get("shuffle", False)

        jellyfin_type = device_state.get("media_item_type", "")
        attrs[Attributes.MEDIA_TYPE] = _JELLYFIN_TYPE_TO_CONTENT_TYPE.get(
            jellyfin_type, MediaContentType.VIDEO if jellyfin_type else ""
        )

        repeat_mode = device_state.get("repeat", "RepeatNone")
        if repeat_mode == "RepeatOne":
            attrs[Attributes.REPEAT] = RepeatMode.ONE
        elif repeat_mode == "RepeatAll":
            attrs[Attributes.REPEAT] = RepeatMode.ALL
        else:
            attrs[Attributes.REPEAT] = RepeatMode.OFF

        current_item_id = device_state.get("media_item_id", "")
        image = device_state.get("media_image", "")
        if image:
            if current_item_id != self._last_media_item_id:
                self._last_media_item_id = current_item_id
            attrs[Attributes.MEDIA_IMAGE_URL] = image
        else:
            attrs[Attributes.MEDIA_IMAGE_URL] = ""
            self._last_media_item_id = ""

        self.update(attrs)

        sensor_state = {
            "state": state_str,
            "media_title": device_state.get("media_title", ""),
            "media_artist": device_state.get("media_artist", ""),
        }
        for sensor in self._sensors:
            await sensor.update_state(sensor_state)

    async def browse(self, options: BrowseOptions) -> BrowseResults | StatusCodes:
        return await browser.browse(self._device, self._device_id, options)

    async def search(self, options: SearchOptions) -> SearchResults | StatusCodes:
        return await browser.search(self._device, self._device_id, options)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        _LOG.info("[%s] Command: %s params=%s", self.id, cmd_id, params)

        try:
            if cmd_id == Commands.PLAY_PAUSE:
                await self._device.play_pause(self._device_id)

            elif cmd_id == Commands.STOP:
                await self._device.stop(self._device_id)

            elif cmd_id == Commands.NEXT:
                await self._device.next_track(self._device_id)

            elif cmd_id == Commands.PREVIOUS:
                await self._device.previous_track(self._device_id)

            elif cmd_id == Commands.VOLUME:
                volume = int(params.get("volume", 50)) if params else 50
                await self._device.set_volume(self._device_id, volume)

            elif cmd_id == Commands.VOLUME_UP:
                await self._device.volume_up(self._device_id)

            elif cmd_id == Commands.VOLUME_DOWN:
                await self._device.volume_down(self._device_id)

            elif cmd_id == Commands.MUTE_TOGGLE:
                await self._device.mute_toggle(self._device_id)

            elif cmd_id == Commands.SEEK:
                if params and "media_position" in params:
                    position = int(params["media_position"])
                    success = await self._device.seek(self._device_id, position)
                    if success:
                        self.set_media_position(position, update=True)
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            elif cmd_id == Commands.FAST_FORWARD:
                current = self.media_position or 0
                duration = self.media_duration or 0
                new_pos = min(current + FF_RW_SECONDS, duration) if duration else current + FF_RW_SECONDS
                await self._device.seek(self._device_id, new_pos)

            elif cmd_id == Commands.REWIND:
                current = self.media_position or 0
                new_pos = max(current - FF_RW_SECONDS, 0)
                await self._device.seek(self._device_id, new_pos)

            elif cmd_id == Commands.REPEAT:
                repeat = params.get("repeat", "OFF") if params else "OFF"
                await self._device.send_command(
                    self._device_id, f"SetRepeatMode {repeat}"
                )

            elif cmd_id == Commands.SHUFFLE:
                shuffle = params.get("shuffle", False) if params else False
                mode = "Shuffled" if shuffle else "Sorted"
                await self._device.send_command(
                    self._device_id, f"SetShuffleQueue {mode}"
                )

            elif cmd_id == Commands.PLAY_MEDIA:
                return await self._handle_play_media(params)

            else:
                _LOG.warning("[%s] Unhandled command: %s", self.id, cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

            await asyncio.sleep(0.5)
            await self.sync_state()
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
            success = await self._device.play_item(self._device_id, item_id)
            if success:
                await asyncio.sleep(1)
                await self.sync_state()
            return StatusCodes.OK if success else StatusCodes.SERVER_ERROR

        _LOG.warning("[%s] Unknown media_id: %s", self.id, media_id)
        return StatusCodes.BAD_REQUEST
