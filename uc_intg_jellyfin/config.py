"""
Configuration Management for Jellyfin Integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MIT, see LICENSE for more details.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

_LOG = logging.getLogger(__name__)

class Config:
    """Configuration management for Jellyfin integration."""

    def __init__(self, config_dir: str = None):
        """Initialize configuration manager."""
        if config_dir is None:
            config_dir = os.getenv("UC_CONFIG_HOME", ".")
        
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "config.json")
        self._data: Dict[str, Any] = {}
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)

    def load(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                _LOG.info("Configuration loaded from %s", self.config_file)
            else:
                _LOG.info("No configuration file found, using defaults")
                self._data = {}
        except Exception as e:
            _LOG.error("Failed to load configuration: %s", e)
            self._data = {}

    def save(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2)
            _LOG.info("Configuration saved to %s", self.config_file)
        except Exception as e:
            _LOG.error("Failed to save configuration: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value."""
        self._data[key] = value

    def is_configured(self) -> bool:
        """Check if integration is properly configured."""
        required_fields = ["host", "username", "password"]
        return all(self.get(field) for field in required_fields)

    def get_host(self) -> Optional[str]:
        """Get Jellyfin server host/URL."""
        return self.get("host")

    def get_username(self) -> Optional[str]:
        """Get Jellyfin username."""
        return self.get("username")

    def get_password(self) -> Optional[str]:
        """Get Jellyfin password."""
        return self.get("password")

    def get_server_id(self) -> Optional[str]:
        """Get Jellyfin server ID."""
        return self.get("server_id")

    def get_user_id(self) -> Optional[str]:
        """Get Jellyfin user ID."""
        return self.get("user_id")

    def set_server_info(self, server_info: Dict[str, Any]):
        """Store server information."""
        self.set("server_info", server_info)
        if "Id" in server_info:
            self.set("server_id", server_info["Id"])

    def set_user_info(self, user_id: str):
        """Store user information."""
        self.set("user_id", user_id)

    def clear(self):
        """Clear all configuration."""
        self._data = {}
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        _LOG.info("Configuration cleared")

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._data.copy()