"""
Constants for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

POLL_INTERVAL = 5
PERIODIC_REFRESH_INTERVAL = 10
WATCHDOG_INTERVAL = 60
RECONNECT_DELAY = 10
CONNECT_RETRIES = 3
CONNECT_RETRY_DELAY = 3
TICKS_PER_SECOND = 10_000_000
FF_RW_SECONDS = 30

KEY_MAP = {
    "UP": "MoveUp",
    "DOWN": "MoveDown",
    "LEFT": "MoveLeft",
    "RIGHT": "MoveRight",
    "SELECT": "Select",
    "BACK": "Back",
    "HOME": "GoHome",
    "MENU": "ToggleContextMenu",
    "INFO": "ToggleOsd",
    "SETTINGS": "GoToSettings",
    "PLAYPAUSE": "PlayPause",
    "STOP": "Stop",
    "NEXT": "NextTrack",
    "PREVIOUS": "PreviousTrack",
    "VOLUME_UP": "VolumeUp",
    "VOLUME_DOWN": "VolumeDown",
    "MUTE": "ToggleMute",
}

SIMPLE_COMMANDS = [
    "UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK", "HOME",
    "PLAYPAUSE", "STOP", "NEXT", "PREVIOUS",
    "VOLUME_UP", "VOLUME_DOWN", "MUTE",
    "MENU", "INFO", "SETTINGS",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
]
