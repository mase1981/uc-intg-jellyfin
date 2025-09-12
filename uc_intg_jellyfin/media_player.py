"""
Jellyfin media player entity implementation using official client.

:copyright: (c) 2025 by Meir Miyara.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import ucapi
from ucapi import MediaPlayer

from uc_intg_jellyfin.client import JellyfinClient

_LOG = logging.getLogger(__name__)


class JellyfinMediaPlayer(MediaPlayer):
    """Jellyfin media player entity using official client."""
    
    def __init__(self, session_data: Dict[str, Any], shared_client: JellyfinClient, entity_id: str):
        """Initialize Jellyfin media player with SHARED CLIENT."""
        self._session_id = session_data.get('Id')
        self._session_data = session_data
        self._client = shared_client
        
        # State management
        self._attr_state = ucapi.media_player.States.OFF
        self._attr_volume = 0
        self._attr_muted = False
        self._attr_media_position = 0
        self._attr_media_duration = 0
        self._attr_media_title = ""
        self._attr_media_artist = ""
        self._attr_media_album = ""
        self._attr_media_image_url = ""
        self._attr_repeat = ucapi.media_player.RepeatMode.OFF
        self._attr_shuffle = False
        
        self._update_task: Optional[asyncio.Task] = None
        self._connected = True  # Always connected since using shared client
        self._monitoring = False
        self._integration_api = None
        
        # Clean entity name (no username, no UUIDs)
        client_name = session_data.get('Client', 'Unknown')
        device_name = session_data.get('DeviceName', '')
        
        if device_name and device_name != client_name:
            entity_name = f"{client_name} ({device_name})"
        else:
            entity_name = f"{client_name}"
        
        features = [
            # Basic playback control
            ucapi.media_player.Features.PLAY_PAUSE,
            ucapi.media_player.Features.STOP,
            
            # Track navigation
            ucapi.media_player.Features.NEXT,
            ucapi.media_player.Features.PREVIOUS,
            
            # Volume control
            ucapi.media_player.Features.VOLUME,
            ucapi.media_player.Features.MUTE_TOGGLE,
            
            # Seeking functionality
            ucapi.media_player.Features.SEEK,
            ucapi.media_player.Features.FAST_FORWARD,
            ucapi.media_player.Features.REWIND,
            
            # Media information display
            ucapi.media_player.Features.MEDIA_TITLE,
            ucapi.media_player.Features.MEDIA_ARTIST,
            ucapi.media_player.Features.MEDIA_ALBUM,
            ucapi.media_player.Features.MEDIA_IMAGE_URL,
            ucapi.media_player.Features.MEDIA_POSITION,
            ucapi.media_player.Features.MEDIA_DURATION,
        ]
        
        # Initial attributes
        attributes = {
            ucapi.media_player.Attributes.STATE: self._attr_state,
            ucapi.media_player.Attributes.VOLUME: self._attr_volume,
            ucapi.media_player.Attributes.MUTED: self._attr_muted,
            ucapi.media_player.Attributes.MEDIA_POSITION: self._attr_media_position,
            ucapi.media_player.Attributes.MEDIA_DURATION: self._attr_media_duration,
            ucapi.media_player.Attributes.MEDIA_TITLE: self._attr_media_title,
            ucapi.media_player.Attributes.MEDIA_ARTIST: self._attr_media_artist,
            ucapi.media_player.Attributes.MEDIA_ALBUM: self._attr_media_album,
            ucapi.media_player.Attributes.MEDIA_IMAGE_URL: self._attr_media_image_url,
            ucapi.media_player.Attributes.REPEAT: self._attr_repeat,
            ucapi.media_player.Attributes.SHUFFLE: self._attr_shuffle
        }
        
        super().__init__(
            entity_id,
            entity_name,
            features,
            attributes,
            device_class=ucapi.media_player.DeviceClasses.STREAMING_BOX,
            cmd_handler=self.command_handler
        )
    
    async def command_handler(self, entity, cmd_id: str, params: Dict[str, Any] = None) -> ucapi.StatusCodes:
        """Handle media player commands using only supported ucapi commands."""
        _LOG.info("Media Player Command: %s for session %s", cmd_id, self._session_id)
        
        if not self._connected:
            _LOG.error("Cannot execute command - client not connected")
            return ucapi.StatusCodes.SERVICE_UNAVAILABLE
        
        try:
            success = False
            
            # Basic playback commands
            if cmd_id == ucapi.media_player.Commands.PLAY_PAUSE:
                success = await self._client.play_pause_toggle(self._session_id)
                _LOG.info("Sent PLAY_PAUSE command")
                    
            elif cmd_id == ucapi.media_player.Commands.STOP:
                success = await self._client.stop_session(self._session_id)
                _LOG.info("Sent STOP command")
            
            # Track navigation commands
            elif cmd_id == ucapi.media_player.Commands.NEXT:
                success = await self._client.next_track(self._session_id)
                _LOG.info("Sent NEXT command")
                
            elif cmd_id == ucapi.media_player.Commands.PREVIOUS:
                success = await self._client.previous_track(self._session_id)
                _LOG.info("Sent PREVIOUS command")
            
            # Volume commands
            elif cmd_id == ucapi.media_player.Commands.VOLUME:
                volume = params.get("volume", 50) if params else 50
                success = await self._client.set_volume(self._session_id, volume)
                _LOG.info("Sent VOLUME command: %d", volume)
                
            elif cmd_id == ucapi.media_player.Commands.MUTE_TOGGLE:
                success = await self._client.toggle_mute(self._session_id)
                _LOG.info("Sent MUTE_TOGGLE command")
            
            # Seeking commands
            elif cmd_id == ucapi.media_player.Commands.SEEK:
                position = params.get("position", 0) if params else 0
                position_ticks = int(position * 10000000)  # Convert seconds to ticks
                success = await self._client.seek(self._session_id, position_ticks)
                _LOG.info("Sent SEEK command: %d seconds", position)
                
            elif cmd_id == ucapi.media_player.Commands.FAST_FORWARD:
                # Fast forward by 30 seconds
                current_position = self._attr_media_position
                new_position = min(current_position + 30, self._attr_media_duration)
                position_ticks = int(new_position * 10000000)
                success = await self._client.seek(self._session_id, position_ticks)
                _LOG.info("Sent FAST_FORWARD command: +30s to %d seconds", new_position)
                
            elif cmd_id == ucapi.media_player.Commands.REWIND:
                # Rewind by 30 seconds
                current_position = self._attr_media_position
                new_position = max(current_position - 30, 0)
                position_ticks = int(new_position * 10000000)
                success = await self._client.seek(self._session_id, position_ticks)
                _LOG.info("Sent REWIND command: -30s to %d seconds", new_position)
            
            # Repeat and shuffle commands
            elif cmd_id == ucapi.media_player.Commands.REPEAT:
                repeat_mode = params.get("repeat", "OFF") if params else "OFF"
                success = await self._client.set_repeat_mode(self._session_id, repeat_mode)
                _LOG.info("Sent REPEAT command: %s", repeat_mode)
                
            elif cmd_id == ucapi.media_player.Commands.SHUFFLE:
                shuffle_mode = params.get("shuffle", False) if params else False
                shuffle_str = "Shuffled" if shuffle_mode else "Sorted"
                success = await self._client.set_shuffle_mode(self._session_id, shuffle_str)
                _LOG.info("Sent SHUFFLE command: %s", shuffle_mode)
                
            else:
                _LOG.warning("Unsupported command: %s", cmd_id)
                return ucapi.StatusCodes.NOT_IMPLEMENTED
            
            # Force immediate state update after command
            if success:
                await asyncio.sleep(0.5)  # Brief delay for server to process
                await self.update_attributes()
            
            return ucapi.StatusCodes.OK if success else ucapi.StatusCodes.SERVER_ERROR
            
        except Exception as e:
            _LOG.error("Command execution failed: %s", e)
            return ucapi.StatusCodes.SERVER_ERROR
    
    def connect(self) -> bool:
        """Connect to Jellyfin server - SIMPLIFIED since using shared client."""
        self._connected = True
        _LOG.info("Media player connected using shared client for session %s", self._session_id)
        return True
    
    async def update_status(self) -> None:
        """Update session status from Jellyfin server."""
        if not self._connected:
            _LOG.debug("Not connected, skipping status update for %s", self.id)
            return
            
        try:
            _LOG.debug("Getting session status for %s", self._session_id)
            
            # Get current user sessions using shared client
            sessions = await self._client.get_my_sessions()
            
            # Find our session
            current_session = next((s for s in sessions if s.get('Id') == self._session_id), None)
            
            if not current_session:
                _LOG.warning("Session %s not found. Clearing media info.", self._session_id)
                self._attr_state = ucapi.media_player.States.OFF
                self._attr_media_title = ""
                self._attr_media_artist = ""
                self._attr_media_album = ""
                self._attr_media_position = 0
                self._attr_media_duration = 0
                self._attr_media_image_url = ""
                return
            
            # Update session data
            self._session_data = current_session
            
            # Determine playback state
            play_state = current_session.get('PlayState', {})
            now_playing = current_session.get('NowPlayingItem', {})
            
            # Map playback state
            if play_state.get('IsPaused', False):
                self._attr_state = ucapi.media_player.States.PAUSED
            elif now_playing and not play_state.get('IsPaused', False):
                self._attr_state = ucapi.media_player.States.PLAYING  
            else:
                self._attr_state = ucapi.media_player.States.ON
            
            # Update media info
            if now_playing:
                # Title: Use Name (episode title) or fallback to SeriesName
                self._attr_media_title = now_playing.get('Name', '')
                
                # Artist: Use SeriesName for TV shows, Artists for music
                if now_playing.get('Type') == 'Episode':
                    series_name = now_playing.get('SeriesName', '')
                    season_episode = ""
                    if now_playing.get('ParentIndexNumber') and now_playing.get('IndexNumber'):
                        season_episode = f"S{now_playing['ParentIndexNumber']}E{now_playing['IndexNumber']}"
                    
                    if series_name and season_episode:
                        self._attr_media_artist = f"{series_name} - {season_episode}"
                    elif series_name:
                        self._attr_media_artist = series_name
                    else:
                        self._attr_media_artist = "TV Show"
                elif now_playing.get('Artists'):
                    self._attr_media_artist = ', '.join(now_playing.get('Artists', []))
                else:
                    self._attr_media_artist = ""
                
                # Album: Use Season name for TV, Album for music
                if now_playing.get('Type') == 'Episode' and now_playing.get('SeasonName'):
                    self._attr_media_album = now_playing.get('SeasonName', '')
                elif now_playing.get('Album'):
                    self._attr_media_album = now_playing.get('Album', '')
                else:
                    self._attr_media_album = ""
                
                # Media position/duration
                self._attr_media_position = play_state.get('PositionTicks', 0) // 10000000  # Convert to seconds
                self._attr_media_duration = now_playing.get('RunTimeTicks', 0) // 10000000 if now_playing.get('RunTimeTicks') else 0
                
                # Image URL - Use enhanced client artwork method
                self._attr_media_image_url = self._client.get_artwork_url(now_playing) or ""
            else:
                # No media playing
                self._attr_media_title = ""
                self._attr_media_artist = ""
                self._attr_media_album = ""
                self._attr_media_position = 0
                self._attr_media_duration = 0
                self._attr_media_image_url = ""
            
            # Update volume info
            self._attr_volume = play_state.get('VolumeLevel', 100)
            self._attr_muted = play_state.get('IsMuted', False)
            
            # Update repeat/shuffle
            repeat_mode = play_state.get('RepeatMode', 'RepeatNone')
            if repeat_mode == 'RepeatOne':
                self._attr_repeat = ucapi.media_player.RepeatMode.ONE
            elif repeat_mode == 'RepeatAll':
                self._attr_repeat = ucapi.media_player.RepeatMode.ALL
            else:
                self._attr_repeat = ucapi.media_player.RepeatMode.OFF
                
            self._attr_shuffle = play_state.get('ShuffleMode', 'Sorted') != 'Sorted'
            
            _LOG.debug("Updated media player state: %s, Title: %s, Artist: %s", 
                      self._attr_state, self._attr_media_title, self._attr_media_artist)
            
        except Exception as e:
            _LOG.error("Status update failed for %s: %s", self.id, e)
            self._attr_state = ucapi.media_player.States.UNAVAILABLE
    
    async def update_attributes(self):
        """Update attributes and push to Remote."""
        # First update status from server
        await self.update_status()
        
        # Build attributes dictionary (removed album since feature not declared)
        attributes = {
            ucapi.media_player.Attributes.STATE: self._attr_state,
            ucapi.media_player.Attributes.VOLUME: self._attr_volume,
            ucapi.media_player.Attributes.MUTED: self._attr_muted,
            ucapi.media_player.Attributes.MEDIA_POSITION: self._attr_media_position,
            ucapi.media_player.Attributes.MEDIA_DURATION: self._attr_media_duration,
            ucapi.media_player.Attributes.MEDIA_TITLE: self._attr_media_title,
            ucapi.media_player.Attributes.MEDIA_ARTIST: self._attr_media_artist,
            ucapi.media_player.Attributes.MEDIA_IMAGE_URL: self._attr_media_image_url
        }
        
        # Update the entity's attributes
        self.attributes.update(attributes)
        
        # Force integration API update if available
        if self._integration_api and hasattr(self._integration_api, 'configured_entities'):
            try:
                self._integration_api.configured_entities.update_attributes(self.id, attributes)
                _LOG.debug("Forced integration API update for %s - State: %s", self.id, self._attr_state)
            except Exception as e:
                _LOG.debug("Could not force integration API update: %s", e)
        
        _LOG.info("Attributes updated for %s - State: %s, Title: %s, Artist: %s", 
                  self.id, self._attr_state, self._attr_media_title, self._attr_media_artist)
    
    async def start_monitoring(self):
        """Start periodic monitoring - called during subscription."""
        if not self._monitoring:
            self._monitoring = True
            self._update_task = asyncio.create_task(self._periodic_update())
            _LOG.info("Started monitoring for media player %s", self.id)
    
    async def _periodic_update(self) -> None:
        """Periodically update session status."""
        while self._connected and self._monitoring:
            try:
                await asyncio.sleep(3)  # Update every 3 seconds
                if self._monitoring:  # Check again in case stopped during sleep
                    await self.update_attributes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOG.error("Periodic update error: %s", e)
                if self._monitoring:
                    await asyncio.sleep(10)  # Wait longer on error
    
    def stop_monitoring(self):
        """Stop periodic monitoring."""
        if self._monitoring:
            self._monitoring = False
            if self._update_task and not self._update_task.done():
                self._update_task.cancel()
                self._update_task = None
            _LOG.info("Stopped monitoring for media player %s", self.id)
    
    async def disconnect(self) -> None:
        """Disconnect from Jellyfin server."""
        self.stop_monitoring()
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @property
    def session_id(self) -> str:
        """Get session ID."""
        return self._session_id