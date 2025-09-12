"""
Setup handler for the Jellyfin integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MIT, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, Dict

import ucapi.api_definitions as uc
from ucapi import IntegrationSetupError

from uc_intg_jellyfin.client import JellyfinClient

_LOG = logging.getLogger(__name__)

async def handle_setup(
    setup_request: uc.DriverSetupRequest
) -> uc.SetupAction:
    """
    Handle the driver setup process.

    Tests the connection and authentication, returns success or error.
    """
    host = setup_request.setup_data.get("host")
    username = setup_request.setup_data.get("username") 
    password = setup_request.setup_data.get("password")
    otp_code = setup_request.setup_data.get("otp_code")
    
    if not host or not username or not password:
        _LOG.error("Missing required setup data: host, username, or password.")
        return uc.SetupError(IntegrationSetupError.OTHER, "Missing required fields.")

    _LOG.info("Testing connection to Jellyfin server: %s", host)
    
    client = None
    try:
        # Pass otp_code to the client; it will be None if not provided by user
        client = JellyfinClient(host, username, password, otp=otp_code)
        
        # The connect method now handles the full connection and authentication flow
        if not await client.connect():
            _LOG.error("Connection or authentication failed for user: %s", username)
            return uc.SetupError(
                IntegrationSetupError.AUTHORIZATION_ERROR,
                "Authentication failed. Please check your credentials and 2FA code."
            )
        
        # Get server info for final validation
        server_info = await client.get_server_info()
        if not server_info:
            _LOG.error("Failed to get server information after connecting.")
            return uc.SetupError(IntegrationSetupError.OTHER, "Could not retrieve server info.")
        
        _LOG.info("Setup successful for Jellyfin server: %s", 
                 server_info.get('ServerName', 'Unknown'))
        return uc.SetupComplete()
        
    except Exception as e:
        _LOG.error("An unexpected error occurred during setup: %s", e)
        return uc.SetupError(IntegrationSetupError.OTHER, f"An unexpected error occurred: {e}")
    
    finally:
        if client:
            await client.disconnect()