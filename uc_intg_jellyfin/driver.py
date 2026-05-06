"""
Main integration driver for Jellyfin using ucapi-framework.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ucapi import DeviceStates
from ucapi_framework import BaseIntegrationDriver
from ucapi_framework.device import DeviceEvents

from uc_intg_jellyfin.config import JellyfinConfig
from uc_intg_jellyfin.device import JellyfinDevice
from uc_intg_jellyfin.media_player import JellyfinMediaPlayer
from uc_intg_jellyfin.remote import JellyfinRemote
from uc_intg_jellyfin.sensor import JellyfinNowPlayingSensor, JellyfinStateSensor

_LOG = logging.getLogger(__name__)

_ENTITY_SUFFIXES = ("_remote", "_state", "_now_playing")
_RETRY_DELAYS = [5, 10, 20, 30, 60, 120, 300]


class JellyfinDriver(BaseIntegrationDriver[JellyfinDevice, JellyfinConfig]):

    def __init__(self):
        super().__init__(
            device_class=JellyfinDevice,
            entity_classes=[],
            driver_id="uc_intg_jellyfin",
        )
        self._media_players: dict[str, JellyfinMediaPlayer] = {}
        self._remotes: dict[str, JellyfinRemote] = {}
        self._sensors: dict[str, list] = {}
        self._retry_task: asyncio.Task | None = None
        self._device_to_config: dict[str, str] = {}

    def device_from_entity_id(self, entity_id: str) -> str | None:
        if not entity_id:
            return None
        device_id = entity_id
        if device_id.startswith("media_player."):
            device_id = device_id[len("media_player."):]
        for suffix in _ENTITY_SUFFIXES:
            if device_id.endswith(suffix):
                device_id = device_id[: -len(suffix)]
                break
        return self._device_to_config.get(device_id)

    def entity_type_from_entity_id(self, entity_id: str) -> str | None:
        if not entity_id:
            return None
        if entity_id.startswith("media_player."):
            return "media_player"
        if entity_id.endswith("_remote"):
            return "remote"
        if entity_id.endswith(("_state", "_now_playing")):
            return "sensor"
        return "media_player"

    def sub_device_from_entity_id(self, entity_id: str) -> str | None:
        return None

    def register_available_entities(
        self, device_config: JellyfinConfig, device: JellyfinDevice
    ) -> None:
        _LOG.info(
            "Registering entities for %s (%d devices)",
            device_config.identifier, len(device_config.devices),
        )

        for dev_cfg in device_config.devices:
            self._register_device_entities(dev_cfg, device, device_config)

    def _register_device_entities(
        self, dev_cfg: Any, device: JellyfinDevice, config: JellyfinConfig
    ) -> None:
        device_id = dev_cfg.device_id
        if device_id in self._media_players:
            return

        self._device_to_config[device_id] = config.identifier

        sensors = [
            JellyfinStateSensor(device_id, dev_cfg.name, device, self.api),
            JellyfinNowPlayingSensor(device_id, dev_cfg.name, device, self.api),
        ]
        self._sensors[device_id] = sensors

        mp = JellyfinMediaPlayer(dev_cfg, device)
        mp._api = self.api
        mp.set_sensors(sensors)
        self._media_players[device_id] = mp
        self.api.available_entities.add(mp)

        remote = JellyfinRemote(device_id, dev_cfg.name, device, self.api, mp)
        self._remotes[device_id] = remote
        self.api.available_entities.add(remote)

        for sensor in sensors:
            self.api.available_entities.add(sensor)

        _LOG.info("Created entities for device: %s (%s)", dev_cfg.name, device_id)

    def on_device_removed(self, device_or_config: JellyfinDevice | JellyfinConfig | None) -> None:
        if device_or_config is None:
            self._media_players.clear()
            self._remotes.clear()
            self._sensors.clear()
            self._device_to_config.clear()
            self.api.available_entities.clear()
            return

        config = (
            device_or_config
            if isinstance(device_or_config, JellyfinConfig)
            else device_or_config.config
        )

        for dev_cfg in config.devices:
            device_id = dev_cfg.device_id
            self._device_to_config.pop(device_id, None)

            for store in (self._media_players, self._remotes):
                entity = store.pop(device_id, None)
                if entity:
                    self.api.available_entities.remove(entity.id)

            if device_id in self._sensors:
                for sensor in self._sensors.pop(device_id):
                    self.api.available_entities.remove(sensor.id)

    def _find_entity(self, entity_id: str) -> Any | None:
        for store in (self._media_players, self._remotes):
            for entity in store.values():
                if entity.id == entity_id:
                    return entity

        for sensors in self._sensors.values():
            for sensor in sensors:
                if sensor.id == entity_id:
                    return sensor

        return None

    async def connect_devices(self) -> bool:
        if not self.config_manager:
            return False

        configs = list(self.config_manager.all())
        if not configs:
            await self.api.set_device_state(DeviceStates.DISCONNECTED)
            return True

        success = True
        for config in configs:
            device = self._device_instances.get(config.identifier)
            if device and not device.is_connected:
                if not await device.connect():
                    _LOG.error("Failed to connect: %s", config.identifier)
                    success = False
                else:
                    self._discover_new_devices(device, config)

        if success and self._media_players:
            await self.api.set_device_state(DeviceStates.CONNECTED)
        elif success:
            await self.api.set_device_state(DeviceStates.CONNECTED)
        else:
            await self.api.set_device_state(DeviceStates.ERROR)
            self._start_retry_task()

        return success

    def _discover_new_devices(self, device: JellyfinDevice, config: JellyfinConfig) -> None:
        for session in device.get_active_sessions():
            jf_device_id = session.get("DeviceId", "")
            if not jf_device_id:
                continue
            if config.find_by_jellyfin_id(jf_device_id):
                continue

            client_name = session.get("Client", "Unknown")
            device_name = session.get("DeviceName", "")
            if device_name and device_name != client_name:
                name = f"{client_name} ({device_name})"
            else:
                name = client_name

            new_device_id = config.add_device(jf_device_id, name)
            self.config_manager.update(config)

            dev_cfg = config.get_device(new_device_id)
            if dev_cfg:
                self._register_device_entities(dev_cfg, device, config)
            _LOG.info("Dynamically added device: %s (%s)", name, new_device_id)

    def _start_retry_task(self) -> None:
        if self._retry_task is None or self._retry_task.done():
            self._retry_task = asyncio.create_task(self._retry_connection())

    async def _retry_connection(self) -> None:
        attempt = 0
        while self.config_manager and list(self.config_manager.all()):
            delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
            _LOG.warning("Retrying connection in %ds (attempt #%d)...", delay, attempt + 1)
            await asyncio.sleep(delay)
            try:
                if await self.connect_devices():
                    _LOG.info("Retry successful!")
                    return
            except Exception as err:
                _LOG.error("Retry failed: %s", err)
            attempt += 1
