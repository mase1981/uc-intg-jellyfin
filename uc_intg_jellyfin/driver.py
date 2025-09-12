#!/usr/bin/env python3
"""
Jellyfin integration driver for Unfolded Circle Remote Two/Three.

:copyright: (c) 2025 by Meir Miyara.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
import sys
from typing import Any, List

import ucapi
from ucapi import (
    DeviceStates, Events, IntegrationSetupError, SetupComplete, SetupError
)

from uc_intg_jellyfin.config import Config
from uc_intg_jellyfin.client import JellyfinClient
from uc_intg_jellyfin.media_player import JellyfinMediaPlayer

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOG = logging.getLogger(__name__)

# Global variables
api: ucapi.IntegrationAPI = None
config: Config = None
client: JellyfinClient = None

media_players = {}
entities_ready = False


async def setup_handler(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    """Handle setup requests."""
    global config, client, entities_ready
    
    if isinstance(msg, ucapi.DriverSetupRequest):
        _LOG.info("Setting up Jellyfin integration")
        
        # Extract setup data
        setup_data = msg.setup_data
        host = setup_data.get("host", "").strip()
        username = setup_data.get("username", "").strip() 
        password = setup_data.get("password", "").strip()
        
        if not all([host, username, password]):
            _LOG.error("Missing required setup parameters")
            return SetupError(IntegrationSetupError.OTHER)
        
        # Ensure host has protocol
        if not host.startswith(('http://', 'https://')):
            host = f"http://{host}"
        
        _LOG.info("Testing connection to Jellyfin server: %s", host.replace('http://', '').replace('https://',''))
        
        try:
            # Test connection
            test_client = JellyfinClient(host, username, password)
            if not await test_client.connect():
                _LOG.error("Failed to connect to Jellyfin server")
                await test_client.disconnect()
                return SetupError(IntegrationSetupError.CONNECTION_REFUSED)
            
            # Save configuration
            config.set("host", host)
            config.set("username", username)
            config.set("password", password)
            config.save()
            
            await test_client.disconnect()
            
            _LOG.info("Jellyfin setup completed successfully")
            return SetupComplete()
            
        except Exception as e:
            _LOG.error("Setup failed: %s", e)
            return SetupError(IntegrationSetupError.OTHER)
    
    return SetupError(IntegrationSetupError.OTHER)


async def _initialize_entities():
    """Initialize entities after successful setup or connection."""
    global api, config, client, media_players, entities_ready
    
    if entities_ready:
        _LOG.debug("Entities already initialized")
        return
        
    if not config.get_host():
        _LOG.info("Server not configured, skipping entity initialization")
        return
    
    _LOG.info("Initializing Jellyfin entities...")
    await api.set_device_state(DeviceStates.CONNECTING)
    
    try:
        # Create client instance
        client = JellyfinClient(config.get_host(), config.get_username(), config.get_password())
        
        if not await client.connect():
            _LOG.error("Failed to connect to Jellyfin server during initialization")
            await api.set_device_state(DeviceStates.ERROR)
            return
        
        server_info = await client.get_server_info()
        server_name = server_info.get('ServerName', 'Unknown') if server_info else 'Unknown'
        _LOG.info("Connected to Jellyfin server: %s (ID: %s)", server_name, server_info.get('Id', 'Unknown'))
        
        # Clear existing entities
        media_players.clear()
        
        # Get user sessions and create ONLY media player entities
        sessions = await client.get_my_sessions()
        if not sessions:
            _LOG.warning("No active sessions found")
            entities_ready = True
            await api.set_device_state(DeviceStates.CONNECTED)
            return
        
        # Filter to active sessions only
        active_sessions = [s for s in sessions if s.get('IsActive', False)]
        _LOG.info("Found %d active sessions", len(active_sessions))
        
        # Deduplicate sessions by client+device combination
        seen_combinations = set()
        unique_sessions = []
        
        for session in active_sessions:
            client_name = session.get('Client', 'Unknown')
            device_name = session.get('DeviceName', '') 
            
            combination = f"{client_name}_{device_name}"
            if combination not in seen_combinations:
                seen_combinations.add(combination)
                unique_sessions.append(session)
                _LOG.info("Keeping session: %s on %s", client_name, device_name or client_name)
        
        _LOG.info("Found %d unique active user sessions after deduplication", len(unique_sessions))
        
        # Create media player entities for unique sessions
        for session in unique_sessions:
            session_id = session.get('Id')
            if not session_id:
                continue
                
            # Create entity ID
            server_id = server_info.get('Id', 'jellyfin') if server_info else 'jellyfin'
            media_player_id = f"{server_id}_media_player_{session_id}"
            
            # Create media player entity
            media_player = JellyfinMediaPlayer(session, client, media_player_id)
            media_player._integration_api = api
            
            # Connect and add
            if media_player.connect():  # Synchronous since using shared client
                media_players[session_id] = media_player
                api.available_entities.add(media_player)
                _LOG.info("Created media player entity: %s for %s", media_player_id, media_player.name['en'])
            else:
                _LOG.error("Failed to connect media player for session %s", session_id)
        
        entities_ready = True
        await api.set_device_state(DeviceStates.CONNECTED)
        _LOG.info("Jellyfin integration setup completed successfully - %d media players created", len(media_players))
        
    except Exception as e:
        _LOG.error("Entity initialization failed: %s", e, exc_info=True)
        await api.set_device_state(DeviceStates.ERROR)


async def _monitor_connection():
    """Monitor connection status and reconnect if needed - ENHANCED."""
    global client, api, entities_ready
    
    while True:
        try:
            if client and entities_ready:
                # Test connection with actual API call
                server_info = await client.get_server_info()
                if server_info:
                    # Connection is good
                    if api.device_state != DeviceStates.CONNECTED:
                        _LOG.info("Connection restored - setting state to CONNECTED")
                        await api.set_device_state(DeviceStates.CONNECTED)
                else:
                    # Connection lost
                    _LOG.warning("Connection lost - attempting reconnection")
                    await api.set_device_state(DeviceStates.CONNECTING)
                    
                    # Try to reconnect
                    if await client.connect():
                        _LOG.info("Reconnection successful")
                        await api.set_device_state(DeviceStates.CONNECTED)
                    else:
                        _LOG.error("Reconnection failed")
                        await api.set_device_state(DeviceStates.ERROR)
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            _LOG.error("Connection monitoring error: %s", e)
            await asyncio.sleep(60)  # Wait longer on error


async def on_subscribe_entities(entity_ids: List[str]):
    """Handle entity subscription events - CRITICAL TIMING."""
    global media_players
    
    _LOG.info("Entities subscribed: %s", entity_ids)
    
    for entity_id in entity_ids:
        # Check media players only
        for session_id, media_player in media_players.items():
            if media_player.id == entity_id:
                _LOG.info("Entity subscribed, pushing initial state: %s", entity_id)
                # Add to configured entities
                api.configured_entities.add(media_player)
                # Update initial state
                await media_player.update_attributes()
                # Start monitoring
                await media_player.start_monitoring()
                break
    
    # Background monitoring message
    if not hasattr(on_subscribe_entities, '_monitoring_started'):
        on_subscribe_entities._monitoring_started = True
        _LOG.info("Background monitoring started")


async def on_unsubscribe_entities(entity_ids: List[str]):
    """Handle entity unsubscription."""
    _LOG.info("Entities unsubscribed: %s", entity_ids)
    
    # Stop monitoring for unsubscribed entities
    for entity_id in entity_ids:
        for session_id, media_player in media_players.items():
            if media_player.id == entity_id:
                media_player.stop_monitoring()
                break


async def on_connect():
    """Handle Remote Two connection - ENHANCED."""
    global config
    
    _LOG.info("Remote Two connected")
    
    # Reload configuration from disk for reboot survival
    if not config:
        config = Config()
    config.load()
    
    if config.get_host():
        _LOG.info("Configuration found, initializing entities")
        
        # Check if entities already exist, recreate if missing
        if not entities_ready or not api.available_entities:
            await _initialize_entities()
        else:
            # Entities already ready - just set connected
            await api.set_device_state(DeviceStates.CONNECTED)
        
        # Start connection monitoring task
        asyncio.create_task(_monitor_connection())
    else:
        _LOG.info("No configuration found, waiting for setup")
        await api.set_device_state(DeviceStates.DISCONNECTED)


async def on_disconnect():
    """Handle Remote Two disconnection."""
    _LOG.info("Remote Two disconnected")


async def main():
    """Main entry point."""
    global api, config
    
    _LOG.info("Starting Jellyfin Integration Driver")
    
    try:
        # Load configuration
        config = Config()
        config.load()
        
        # Set up UC API
        driver_path = os.path.join(os.path.dirname(__file__), "..", "driver.json") 
        loop = asyncio.get_running_loop()
        api = ucapi.IntegrationAPI(loop)
        
        # Initialize UC API
        await api.init(driver_path, setup_handler)
        
        # Register event listeners
        api.add_listener(Events.CONNECT, on_connect)
        api.add_listener(Events.DISCONNECT, on_disconnect)
        api.add_listener(Events.SUBSCRIBE_ENTITIES, on_subscribe_entities)
        api.add_listener(Events.UNSUBSCRIBE_ENTITIES, on_unsubscribe_entities)
        
        if config.get_host():
            _LOG.info("Server already configured, will initialize on connection")
        else:
            _LOG.info("Server not configured, waiting for setup...")
            await api.set_device_state(DeviceStates.DISCONNECTED)
        
        # Keep running
        await asyncio.Future()
        
    except Exception as e:
        _LOG.error("Fatal error: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOG.info("Integration stopped by user")
    except Exception as e:
        _LOG.error("Integration crashed: %s", e, exc_info=True)
        sys.exit(1)