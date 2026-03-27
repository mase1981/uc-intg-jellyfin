"""
Remote Control entity for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from ucapi import Remote, StatusCodes
from ucapi.remote import Attributes, Commands, Features, States
from ucapi.ui import (
    Buttons,
    Size,
    UiPage,
    create_btn_mapping,
    create_ui_icon,
    create_ui_text,
)

from uc_intg_jellyfin.const import KEY_MAP, PERIODIC_REFRESH_INTERVAL, SIMPLE_COMMANDS

if TYPE_CHECKING:
    import ucapi
    from uc_intg_jellyfin.device import JellyfinDevice
    from uc_intg_jellyfin.media_player import JellyfinMediaPlayer

_LOG = logging.getLogger(__name__)

BUTTON_MAPPING = [
    create_btn_mapping(Buttons.HOME, short="HOME"),
    create_btn_mapping(Buttons.BACK, short="BACK"),
    create_btn_mapping(Buttons.DPAD_UP, short="UP"),
    create_btn_mapping(Buttons.DPAD_DOWN, short="DOWN"),
    create_btn_mapping(Buttons.DPAD_LEFT, short="LEFT"),
    create_btn_mapping(Buttons.DPAD_RIGHT, short="RIGHT"),
    create_btn_mapping(Buttons.DPAD_MIDDLE, short="SELECT"),
    create_btn_mapping(Buttons.VOLUME_UP, short="VOLUME_UP"),
    create_btn_mapping(Buttons.VOLUME_DOWN, short="VOLUME_DOWN"),
    create_btn_mapping(Buttons.MUTE, short="MUTE"),
    create_btn_mapping(Buttons.PLAY, short="PLAYPAUSE"),
    create_btn_mapping(Buttons.STOP, short="STOP"),
    create_btn_mapping(Buttons.PREV, short="PREVIOUS"),
    create_btn_mapping(Buttons.NEXT, short="NEXT"),
]


def _create_main_page() -> UiPage:
    page = UiPage("main", "Navigation", grid=Size(4, 6))
    page.add(create_ui_icon("uc:up-arrow", 1, 1, cmd="UP"))
    page.add(create_ui_icon("uc:left-arrow", 0, 2, cmd="LEFT"))
    page.add(create_ui_text("OK", 1, 2, size=Size(2, 1), cmd="SELECT"))
    page.add(create_ui_icon("uc:right-arrow", 3, 2, cmd="RIGHT"))
    page.add(create_ui_icon("uc:down-arrow", 1, 3, cmd="DOWN"))
    page.add(create_ui_icon("uc:home", 0, 4, cmd="HOME"))
    page.add(create_ui_icon("uc:back", 1, 4, cmd="BACK"))
    page.add(create_ui_icon("uc:menu", 2, 4, cmd="MENU"))
    page.add(create_ui_text("INFO", 3, 4, cmd="INFO"))
    return page


def _create_media_page() -> UiPage:
    page = UiPage("media", "Media Control", grid=Size(4, 6))
    page.add(create_ui_icon("uc:prev", 0, 1, size=Size(2, 2), cmd="PREVIOUS"))
    page.add(create_ui_icon("uc:next", 2, 1, size=Size(2, 2), cmd="NEXT"))
    page.add(create_ui_text("P/P", 0, 3, size=Size(2, 2), cmd="PLAYPAUSE"))
    page.add(create_ui_icon("uc:stop", 2, 3, size=Size(2, 2), cmd="STOP"))
    page.add(create_ui_text("VOL+", 0, 5, cmd="VOLUME_UP"))
    page.add(create_ui_text("VOL-", 1, 5, cmd="VOLUME_DOWN"))
    page.add(create_ui_text("MUTE", 2, 5, size=Size(2, 1), cmd="MUTE"))
    return page


def _create_numbers_page() -> UiPage:
    page = UiPage("numbers", "Numbers", grid=Size(4, 6))
    page.add(create_ui_text("1", 0, 1, cmd="1"))
    page.add(create_ui_text("2", 1, 1, cmd="2"))
    page.add(create_ui_text("3", 2, 1, cmd="3"))
    page.add(create_ui_text("4", 0, 2, cmd="4"))
    page.add(create_ui_text("5", 1, 2, cmd="5"))
    page.add(create_ui_text("6", 2, 2, cmd="6"))
    page.add(create_ui_text("7", 0, 3, cmd="7"))
    page.add(create_ui_text("8", 1, 3, cmd="8"))
    page.add(create_ui_text("9", 2, 3, cmd="9"))
    page.add(create_ui_text("0", 1, 4, cmd="0"))
    return page


class JellyfinRemote(Remote):

    def __init__(
        self,
        device_id: str,
        device_name: str,
        jellyfin_device: JellyfinDevice,
        api: ucapi.IntegrationAPI,
        media_player: JellyfinMediaPlayer | None = None,
    ) -> None:
        self._device_id = device_id
        self._jellyfin_device = jellyfin_device
        self._api = api
        self._media_player = media_player

        super().__init__(
            identifier=f"{device_id}_remote",
            name=f"{device_name} Remote",
            features=[Features.SEND_CMD],
            attributes={Attributes.STATE: States.UNAVAILABLE},
            simple_commands=SIMPLE_COMMANDS,
            button_mapping=BUTTON_MAPPING,
            ui_pages=[
                _create_main_page(),
                _create_media_page(),
                _create_numbers_page(),
            ],
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
                _LOG.error("Periodic refresh error for remote %s: %s", self._device_id, err)
                await asyncio.sleep(PERIODIC_REFRESH_INTERVAL)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        _LOG.info("[%s] Command: %s params=%s", self.id, cmd_id, params)

        try:
            if cmd_id == Commands.SEND_CMD:
                command = params.get("command") if params else None
                if not command:
                    return StatusCodes.BAD_REQUEST
                await self._dispatch_command(command)
            else:
                return StatusCodes.NOT_IMPLEMENTED

            await self.push_update()
            return StatusCodes.OK

        except Exception as err:
            _LOG.error("[%s] Command error: %s", self.id, err, exc_info=True)
            return StatusCodes.SERVER_ERROR

    async def _dispatch_command(self, command: str) -> None:
        if command == "PLAYPAUSE":
            await self._jellyfin_device.play_pause(self._device_id)
            return
        if command == "STOP":
            await self._jellyfin_device.stop(self._device_id)
            return
        if command == "NEXT":
            await self._jellyfin_device.next_track(self._device_id)
            return
        if command == "PREVIOUS":
            await self._jellyfin_device.previous_track(self._device_id)
            return
        if command == "VOLUME_UP":
            await self._jellyfin_device.volume_up(self._device_id)
            return
        if command == "VOLUME_DOWN":
            await self._jellyfin_device.volume_down(self._device_id)
            return
        if command == "MUTE":
            await self._jellyfin_device.mute_toggle(self._device_id)
            return

        if command in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            await self._jellyfin_device.send_command(
                self._device_id, f"SendString {command}"
            )
            return

        jellyfin_cmd = KEY_MAP.get(command)
        if jellyfin_cmd:
            await self._jellyfin_device.send_command(self._device_id, jellyfin_cmd)
            return

        _LOG.warning("Unknown command: %s, sending as-is", command)
        await self._jellyfin_device.send_command(self._device_id, command)

    async def push_update(self) -> None:
        if not self._api or not self._api.configured_entities.contains(self.id):
            return

        device_state = self._jellyfin_device.get_device_state(self._device_id)
        state = device_state.get("state", "idle")

        if state in ("playing", "paused", "idle"):
            self.attributes[Attributes.STATE] = States.ON
        else:
            self.attributes[Attributes.STATE] = States.UNAVAILABLE

        self._api.configured_entities.update_attributes(self.id, self.attributes)
