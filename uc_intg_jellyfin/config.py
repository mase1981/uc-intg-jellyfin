"""
Configuration for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def make_device_id(jellyfin_device_id: str) -> str:
    return f"jf_{hashlib.md5(jellyfin_device_id.encode()).hexdigest()[:12]}"


@dataclass
class JellyfinDeviceConfig:
    """Configuration for a single Jellyfin client device."""

    device_id: str
    jellyfin_device_id: str
    name: str


@dataclass
class JellyfinConfig:
    """Configuration for a Jellyfin server connection."""

    identifier: str
    name: str
    host: str
    username: str
    password: str
    user_id: str = ""
    server_id: str = ""
    devices: list[JellyfinDeviceConfig] = field(default_factory=list)

    def __post_init__(self):
        converted = []
        for device in self.devices:
            if isinstance(device, dict):
                converted.append(JellyfinDeviceConfig(**device))
            else:
                converted.append(device)
        self.devices = converted

    def add_device(self, jellyfin_device_id: str, name: str) -> str:
        device_id = make_device_id(jellyfin_device_id)
        for existing in self.devices:
            if existing.jellyfin_device_id == jellyfin_device_id:
                existing.name = name
                return device_id
        self.devices.append(JellyfinDeviceConfig(
            device_id=device_id,
            jellyfin_device_id=jellyfin_device_id,
            name=name,
        ))
        return device_id

    def get_device(self, device_id: str) -> JellyfinDeviceConfig | None:
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None

    def find_by_jellyfin_id(self, jellyfin_device_id: str) -> JellyfinDeviceConfig | None:
        for device in self.devices:
            if device.jellyfin_device_id == jellyfin_device_id:
                return device
        return None
