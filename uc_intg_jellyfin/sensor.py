"""
Sensor entities for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from ucapi import Sensor
from ucapi.sensor import Attributes, DeviceClasses, States

if TYPE_CHECKING:
    import ucapi
    from uc_intg_jellyfin.device import JellyfinDevice

_LOG = logging.getLogger(__name__)


class _BaseSensor(Sensor):

    def __init__(
        self,
        entity_id: str,
        name: str,
        jellyfin_device: JellyfinDevice,
        device_id: str,
        api: ucapi.IntegrationAPI,
    ) -> None:
        self._device_id = device_id
        self._jellyfin_device = jellyfin_device
        self._api = api

        super().__init__(
            identifier=entity_id,
            name=name,
            features=[],
            attributes={Attributes.STATE: States.UNAVAILABLE, Attributes.VALUE: ""},
            device_class=DeviceClasses.CUSTOM,
        )

    def _push_if_configured(self) -> None:
        if self._api and self._api.configured_entities.contains(self.id):
            self._api.configured_entities.update_attributes(self.id, self.attributes)

    async def update_state(self, device_state: dict[str, Any]) -> None:
        raise NotImplementedError

    async def push_update(self) -> None:
        state = self._jellyfin_device.get_device_state(self._device_id)
        await self.update_state(state)


class JellyfinStateSensor(_BaseSensor):

    def __init__(
        self, device_id: str, device_name: str, jellyfin_device: JellyfinDevice,
        api: ucapi.IntegrationAPI,
    ) -> None:
        super().__init__(
            f"{device_id}_state", f"{device_name} State",
            jellyfin_device, device_id, api,
        )

    async def update_state(self, device_state: dict[str, Any]) -> None:
        state = device_state.get("state", "idle")
        if state in ("playing", "paused", "idle"):
            self.attributes[Attributes.STATE] = States.ON
            self.attributes[Attributes.VALUE] = state.capitalize()
        else:
            self.attributes[Attributes.STATE] = States.UNAVAILABLE
            self.attributes[Attributes.VALUE] = "Unknown"
        self._push_if_configured()


class JellyfinNowPlayingSensor(_BaseSensor):

    def __init__(
        self, device_id: str, device_name: str, jellyfin_device: JellyfinDevice,
        api: ucapi.IntegrationAPI,
    ) -> None:
        super().__init__(
            f"{device_id}_now_playing", f"{device_name} Now Playing",
            jellyfin_device, device_id, api,
        )

    async def update_state(self, device_state: dict[str, Any]) -> None:
        title = device_state.get("media_title", "")
        artist = device_state.get("media_artist", "")
        if title and artist:
            value = f"{title} - {artist}"
        elif title:
            value = title
        else:
            value = "Nothing Playing"

        self.attributes[Attributes.STATE] = States.ON
        self.attributes[Attributes.VALUE] = value
        self._push_if_configured()
