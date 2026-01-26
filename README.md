# Jellyfin Integration for Unfolded Circle Remote 2/3

Control your Jellyfin media server directly from your Unfolded Circle Remote 2 or Remote 3 with comprehensive media player functionality.

![Jellyfin](https://img.shields.io/badge/Jellyfin-Media%20Server-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-jellyfin?style=flat-square)](https://github.com/mase1981/uc-intg-jellyfin/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-jellyfin?style=flat-square)](https://github.com/mase1981/uc-intg-jellyfin/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-jellyfin/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)


## Features

This integration provides Currently Playing Media and Basic Controls of your Jellyfin media server directly from your Unfolded Circle Remote.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

### 🎵 **Media Player Control**

#### **Playback Control**
- **Play/Pause Toggle** - Seamless playback control with visual feedback
- **Stop** - Stop current playback and clear now playing
- **Previous/Next Track** - Navigate through your media collection
- **Fast Forward/Rewind** - 30-second skip controls for easy navigation
- **Track Control** - Previous/Next track navigation

### 📺 **Media Information Display**

#### **Dynamic Status Information**
Real-time display of media and playback status:
- **Media State** - Playing, paused, stopped with visual indicators
- **Current Media** - Title, series information, episode details
- **Artwork Display** - High-quality poster/thumbnail display with smart fallbacks
- **Progress Information** - Current position and total duration

#### **Smart Metadata Handling**
- **TV Shows** - Series name, season/episode numbers, episode titles
- **Movies** - Movie title, year, genre information
- **Music** - Artist, album, track information
- **Enhanced Titles** - Intelligent parsing of metadata for optimal display

### **Server Requirements**

- **Jellyfin Server** - Version 10.6.4 or higher recommended
- **Network Access** - HTTP/HTTPS connectivity to Jellyfin server
- **Authentication** - Username/password authentication required
- **API Access** - Jellyfin HTTP API access (default on all installations)
- **2FA Support** - Integration supports optional 2FA

### **Network Requirements**

- **Local Network Access** - Integration requires same network as Jellyfin server
- **Firewall Configuration** - Ensure Jellyfin port (default 8096) is accessible
- **TLS/SSL Support** - Supports both HTTP and HTTPS connections

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-jellyfin/releases) page
2. Download the latest `uc-intg-jellyfin-<version>-aarch64.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image from GitHub Container Registry:

**Image**: `ghcr.io/mase1981/uc-intg-jellyfin:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-jellyfin:
    image: ghcr.io/mase1981/uc-intg-jellyfin:latest
    container_name: uc-intg-jellyfin
    network_mode: host
    volumes:
      - </local/path>:/data
    environment:
      - UC_CONFIG_HOME=/data
      - UC_INTEGRATION_HTTP_PORT=9090
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - PYTHONPATH=/app
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-jellyfin --restart unless-stopped --network host -v jellyfin-config:/app/config -e UC_CONFIG_HOME=/app/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9090 -e PYTHONPATH=/app ghcr.io/mase1981/uc-intg-jellyfin:latest
```

## Configuration

### Step 1: Prepare Your Jellyfin Server

**IMPORTANT**: Jellyfin server must be running and accessible on your network before setting up the integration.

#### Server Setup:
1. Ensure Jellyfin server is running and accessible
2. Note the server's IP address and port (default: 8096)
3. Verify you can access the web interface at `http://server-ip:8096`

#### User Account:
1. Create or use existing Jellyfin user account
2. Ensure account has media library access
3. Verify account can control media playback
4. Note username and password for integration setup

#### Network Requirements:
- **Wired Connection** - Recommended for stability
- **Static IP** - Recommended via DHCP reservation
- **Firewall** - Allow HTTP/HTTPS traffic on Jellyfin port
- **Network Isolation** - Must be on same subnet as Remote

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The Jellyfin integration should appear in **Available Integrations**
3. Click **"Configure"** to begin setup:

#### **Configuration:**
- **Server URL** - Your Jellyfin server URL (e.g., http://192.168.1.100:8096)
- **Username** - Your Jellyfin username
- **Password** - Your Jellyfin password
- **2FA** - Optional two-factor authentication
- Click **Complete Setup**

#### **Connection Test:**
- Integration verifies server connectivity
- Authenticates with provided credentials
- Setup fails if server unreachable or credentials invalid

4. Integration will create entities:
   - **[Client Name]** - Media player entity for each active session

## Using the Integration

### Media Player Entity

The media player entity provides complete playback control:

- **Playback Control** - Play/Pause, Stop, Previous, Next
- **Navigation** - Fast Forward, Rewind (30-second skips)
- **Media Information** - Title, series, episode details
- **Artwork Display** - High-quality poster/thumbnail
- **Progress Tracking** - Current position and duration
- **State Monitoring** - Playing, paused, stopped indicators

### Smart Metadata Display

- **TV Shows** - Series name, S01E01 format, episode titles
- **Movies** - Movie title, year, genre
- **Music** - Artist, album, track information
- **Enhanced Titles** - Intelligent metadata parsing

### Adding to Activities

1. Go to **Activities** in your remote interface
2. Edit or create an activity
3. Add Jellyfin entities from **Available Entities** list
4. Configure button mappings and UI layout as desired
5. Save your activity

## Credits

- **Developer** - Meir Miyara
- **Jellyfin** - Free Software Media System
- **Unfolded Circle** - Remote 2/3 integration framework (ucapi)
- **Community** - Testing and feedback from UC community

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Support & Community

- **GitHub Issues** - [Report bugs and request features](https://github.com/mase1981/uc-intg-jellyfin/issues)
- **UC Community Forum** - [General discussion and support](https://unfolded.community/)
- **Developer** - [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You** - Meir Miyara
