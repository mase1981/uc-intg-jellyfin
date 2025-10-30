"""
Jellyfin API client using official jellyfin-apiclient-python library.

:copyright: (c) 2025 by Meir Miyara.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
import socket
from typing import Any, Dict, List, Optional

from jellyfin_apiclient_python import Jellyfin, JellyfinClient as OfficialJellyfinClient
from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

_LOG = logging.getLogger(__name__)


class JellyfinClient:
    """Jellyfin API client using official jellyfin-apiclient-python library."""
    
    def __init__(self, host: str, username: str, password: str, otp: Optional[str] = None):
        """Initialize Jellyfin client."""
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.otp = otp
        
        self._jellyfin = Jellyfin()
        self._client = self._jellyfin.get_client()
        
        device_id = "jellyfin-integration-ucapi"
        device_name = socket.gethostname()
        app_name = "Jellyfin Integration"
        app_version = "1.0.1"
        user_agent = "Jellyfin-Integration/1.0.1"
        
        self._client.config.app(app_name, app_version, device_name, device_id)
        self._client.config.http(user_agent)
        
        self._is_connected = False
        self._user_id: Optional[str] = None
        
    async def connect(self) -> bool:
        """Connect and authenticate with Jellyfin server."""
        try:
            self._client.config.data["auth.ssl"] = self.host.startswith("https")
            
            _LOG.debug("Connecting to Jellyfin server: %s", self.host)
            connect_result = self._client.auth.connect_to_address(self.host)
            
            if CONNECTION_STATE(connect_result["State"]) != CONNECTION_STATE.ServerSignIn:
                _LOG.error("Failed to connect to server")
                return False
            
            _LOG.debug("Authenticating user: %s", self.username)

            if self.otp:
                _LOG.debug("Attempting login with 2FA code.")
                auth_result = self._client.auth.login(
                    self.host, 
                    self.username, 
                    self.password, 
                    otp=self.otp
                )
            else:
                _LOG.debug("Attempting login without 2FA code.")
                auth_result = self._client.auth.login(
                    self.host, 
                    self.username, 
                    self.password
                )

            if "AccessToken" not in auth_result:
                _LOG.error("Authentication failed - no access token. Check credentials and 2FA code if applicable.")
                return False
            
            user_settings = self._client.jellyfin.get_user_settings()
            self._user_id = user_settings["Id"]
            
            self._is_connected = True
            _LOG.info("Successfully connected to Jellyfin server")
            return True
            
        except Exception as e:
            _LOG.error("Connection failed: %s", e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Jellyfin server."""
        self._is_connected = False
        self._user_id = None
        if hasattr(self._client, 'stop'):
            self._client.stop()
    
    async def get_server_info(self) -> Optional[Dict[str, Any]]:
        """Get server information."""
        if not self._is_connected:
            return None
        try:
            return self._client.jellyfin.get_system_info()
        except Exception as e:
            _LOG.error("Failed to get server info: %s", e)
            return None
    
    async def get_my_sessions(self) -> List[Dict[str, Any]]:
        """Get sessions for the authenticated user only."""
        if not self._is_connected:
            _LOG.error("Not connected - cannot get sessions")
            return []
        
        try:
            _LOG.debug("Getting all sessions from server...")
            all_sessions = self._client.jellyfin.sessions()
            
            if not all_sessions:
                _LOG.warning("No sessions returned from server")
                return []
            
            _LOG.debug("Total sessions from server: %d", len(all_sessions))
            
            if self._user_id:
                user_sessions = [s for s in all_sessions if s.get('UserId') == self._user_id]
                _LOG.debug("Sessions for user ID %s: %d", self._user_id, len(user_sessions))
            else:
                user_sessions = []
                _LOG.warning("No user ID available for filtering")
            
            if not user_sessions and self.username:
                user_sessions = [s for s in all_sessions if s.get('UserName') == self.username]
                _LOG.debug("Sessions for username %s: %d", self.username, len(user_sessions))
            
            _LOG.info("Returning %d sessions for integration", len(user_sessions))
            return user_sessions
            
        except Exception as e:
            _LOG.error("Failed to get sessions: %s", e, exc_info=True)
            return []
    
    async def play_session(self, session_id: str) -> bool:
        """Send play command to session."""
        try:
            self._client.jellyfin.remote_unpause(session_id)
            _LOG.debug("Sent play command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send play command: %s", e)
            return False
    
    async def pause_session(self, session_id: str) -> bool:
        """Send pause command to session."""
        try:
            self._client.jellyfin.remote_pause(session_id)
            _LOG.debug("Sent pause command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send pause command: %s", e)
            return False
    
    async def stop_session(self, session_id: str) -> bool:
        """Send stop command to session."""
        try:
            self._client.jellyfin.remote_stop(session_id)
            _LOG.debug("Sent stop command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send stop command: %s", e)
            return False
    
    async def next_track(self, session_id: str) -> bool:
        """Send next track command to session."""
        try:
            self._client.jellyfin.command(session_id, "PlayNext")
            _LOG.debug("Sent next track command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send next track command: %s", e)
            return False
    
    async def previous_track(self, session_id: str) -> bool:
        """Send previous track command to session."""
        try:
            self._client.jellyfin.command(session_id, "PreviousLetter")
            _LOG.debug("Sent previous track command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send previous track command: %s", e)
            return False
    
    async def seek(self, session_id: str, position_ticks: int) -> bool:
        """Seek to position in session."""
        try:
            self._client.jellyfin.remote_seek(session_id, position_ticks)
            _LOG.debug("Sent seek command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send seek command: %s", e)
            return False
    
    async def set_volume(self, session_id: str, volume: int) -> bool:
        """Set volume for session."""
        try:
            self._client.jellyfin.remote_set_volume(session_id, volume)
            _LOG.debug("Sent set volume command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send set volume command: %s", e)
            return False
    
    async def volume_up(self, session_id: str) -> bool:
        """Increase volume for session."""
        try:
            self._client.jellyfin.command(session_id, "VolumeUp")
            _LOG.debug("Sent volume up command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send volume up command: %s", e)
            return False
    
    async def volume_down(self, session_id: str) -> bool:
        """Decrease volume for session."""
        try:
            self._client.jellyfin.command(session_id, "VolumeDown")
            _LOG.debug("Sent volume down command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send volume down command: %s", e)
            return False
    
    async def toggle_mute(self, session_id: str) -> bool:
        """Toggle mute for session."""
        try:
            self._client.jellyfin.command(session_id, "ToggleMute")
            _LOG.debug("Sent toggle mute command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send toggle mute command: %s", e)
            return False
    
    async def mute_session(self, session_id: str) -> bool:
        """Mute session."""
        try:
            self._client.jellyfin.remote_mute(session_id)
            _LOG.debug("Sent mute command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send mute command: %s", e)
            return False
    
    async def unmute_session(self, session_id: str) -> bool:
        """Unmute session."""
        try:
            self._client.jellyfin.remote_unmute(session_id)
            _LOG.debug("Sent unmute command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send unmute command: %s", e)
            return False
    
    async def play_pause_toggle(self, session_id: str) -> bool:
        """Toggle play/pause for session."""
        try:
            self._client.jellyfin.remote_playpause(session_id)
            _LOG.debug("Sent play/pause toggle command to session %s", session_id)
            return True
        except Exception as e:
            _LOG.error("Failed to send play/pause toggle command: %s", e)
            return False
    
    def get_artwork_url(self, item: Dict[str, Any], max_width: int = 600) -> Optional[str]:
        """Get best artwork URL for an item, preferring Backdrop over Primary.

        Priority:
        - Episodes: Series Backdrop > Episode Backdrop > Series Primary > Season Primary > Episode Primary
        - Movies/Other: Item Backdrop > Item Primary
        """
        if not self._is_connected:
            return None
        
        try:
            artwork_id = None
            artwork_type = None
            
            if item.get("Type") == "Episode":
                series_id = item.get("SeriesId")
                if series_id and item.get("SeriesBackdropImageTags"):
                    artwork_id = series_id
                    artwork_type = "Backdrop"
                    _LOG.debug("Using Series Backdrop image for episode")
                elif item.get("BackdropImageTags"):
                    artwork_id = item["Id"]
                    artwork_type = "Backdrop"
                    _LOG.debug("Using Episode Backdrop image")
                elif series_id and item.get("SeriesPrimaryImageTag"):
                    artwork_id = series_id
                    artwork_type = "Primary"
                    _LOG.debug("Using Series Primary image for episode")
                elif item.get("SeasonId"):
                    artwork_id = item.get("SeasonId")
                    artwork_type = "Primary"
                    _LOG.debug("Using Season Primary image for episode")
                elif "Primary" in item.get("ImageTags", {}):
                    artwork_id = item["Id"]
                    artwork_type = "Primary"
                    _LOG.debug("Using Episode Primary image")
            else:
                if item.get("BackdropImageTags"):
                    artwork_type = "Backdrop"
                    artwork_id = item["Id"]
                    _LOG.debug("Using Item Backdrop image")
                elif "Primary" in item.get("ImageTags", {}):
                    artwork_type = "Primary"
                    artwork_id = item["Id"]
                    _LOG.debug("Using Item Primary image")
            
            if artwork_id and artwork_type:
                url = str(self._client.jellyfin.artwork(artwork_id, artwork_type, max_width))
                _LOG.debug("Generated artwork URL: %s", url)
                return url
            else:
                _LOG.debug("No suitable artwork found for item")
                return None
                
        except Exception as e:
            _LOG.error("Failed to get artwork URL: %s", e)
            return None
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected
    
    @property
    def user_id(self) -> Optional[str]:
        """Get authenticated user ID."""
        return self._user_id