# Jellyfin Integration for Unfolded Circle Remote 2/3

Control your Jellyfin media server directly from your Unfolded Circle Remote 2 or Remote 3 with comprehensive media player functionality.

![Jellyfin](https://img.shields.io/badge/Jellyfin-Media%20Server-blue)
![Version](https://img.shields.io/badge/version-1.0.0-green)
![License](https://img.shields.io/badge/license-MPL--2.0-blue)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA)](https://github.com/sponsors/mase1981/button)

## Features

This integration provides Currently Playing Media and Basic Controls of your Jellyfin media server directly from your Unfolded Circle Remote.

### 🎵 **Media Player Control**


#### **Playback Control**
- **Play/Pause Toggle** - Seamless playback control with visual feedback
- **Stop** - Stop current playback and clear now playing
- **Previous/Next Track** - Navigate through your media collection
- **Fast Forward/Next/Rewind/Previous** - 30-second skip controls for easy navigation and Track Control

### 📺 **Media Information Display**

#### **Dynamic Status Information**
Real-time display of media and playback status:
- **Media State**: Playing, paused, stopped with visual indicators
- **Current Media**: Title, series information, episode details
- **Artwork Display**: High-quality poster/thumbnail display with smart fallbacks
- **Progress Information**: Current position and total duration

#### **Smart Metadata Handling**
- **TV Shows**: Series name, season/episode numbers, episode titles
- **Movies**: Movie title, year, genre information
- **Music**: Artist, album, track information
- **Enhanced Titles**: Intelligent parsing of metadata for optimal display

### **Server Requirements**
- **Jellyfin Server**: Version 10.6.4 or higher recommended
- **Network Access**: HTTP/HTTPS connectivity to Jellyfin server
- **Authentication**: Username/password authentication required
- **API Access**: Jellyfin HTTP API access (default on all installations)
- **2FA Support**: Integration support optional 2FA

### **Network Requirements**
- **Local Network Access** - Integration requires same network as Jellyfin server
- **Firewall Configuration** - Ensure Jellyfin port (default 8096) is accessible
- **TLS/SSL Support** - Supports both HTTP and HTTPS connections

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-jellyfin/releases) page
2. Download the latest `uc-intg-jellyfin-<version>.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image from GitHub Container Registry:

**Image**: `ghcr.io/mmiyara/uc-intg-jellyfin:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-jellyfin:
    image: ghcr.io/mase1981/uc-intg-jellyfin:latest
    container_name: uc-intg-jellyfin
    network_mode: host
    volumes:
      - </local/path>:/config
    environment:
      - UC_INTEGRATION_HTTP_PORT=9090
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name=uc-intg-jellyfin --network host -v </local/path>:/config --restart unless-stopped ghcr.io/makse1981/uc-intg-jellyfin:latest
```

## Configuration

### Step 1: Prepare Your Jellyfin Server

1. **Server Setup:**
   - Ensure Jellyfin server is running and accessible on your network
   - Note the server's IP address and port (default: 8096)
   - Verify you can access the web interface at `http://server-ip:8096`

2. **User Account:**
   - Create or use existing Jellyfin user account
   - Ensure account has media library access
   - Verify account can control media playback
   - Note username and password for integration setup

3. **Network Requirements:**
   - Server and Remote must be on same local network
   - Standard HTTP/HTTPS communication on configured port
   - No additional firewall configuration required

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The Jellyfin integration should appear in **Available Integrations**
3. Click **"Configure"** and follow the setup wizard:

   **Server Connection:**
   - **Server URL**: Your Jellyfin server URL (e.g., http://192.168.1.100:8096)
   - **Username**: Your Jellyfin username
   - **Password**: Your Jellyfin password
   - **2FA**: Optional

5. Click **"Complete Setup"** when connection is successful
6. Media player entity will be created for each active session:
   - **[Client Name]** (Media Player Entity)

### Step 3: Add Entities to Activities

1. Go to **Activities** in your remote interface
2. Edit or create an activity
3. Add Jellyfin entities from the **Available Entities** list:
   - **Jellyfin Media Player** - Primary control interface
4. Configure button mappings and UI layout as desired
5. Save your activity

### Debug Information

Enable detailed logging for troubleshooting:

**Docker Environment:**
```bash
# Add to docker-compose.yml environment section
- LOG_LEVEL=DEBUG

# View logs
docker logs uc-intg-jellyfin
```

**Integration Logs:**
- **Remote Interface**: Settings → Integrations → Jellyfin → View Logs
- **Common Errors**: Connection timeouts, authentication failures, session detection issues

**Server Verification:**
- **Web Interface**: Verify server accessible at `http://server-ip:8096`
- **API Test**: Visit `http://server-ip:8096/health` for server status
- **Session Check**: View active sessions in Jellyfin dashboard


## For Developers

### Local Development

1. **Clone and setup:**
   ```bash
   git clone https://github.com/mase1981/uc-intg-jellyfin.git
   cd uc-intg-jellyfin
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Integration uses environment variables and config files:
   ```bash
   export UC_CONFIG_HOME=./config
   # Config automatically created during setup
   ```

3. **Run development:**
   ```bash
   python uc_intg_jellyfin/driver.py
   # Integration runs on localhost:9090
   ```

4. **VS Code debugging:**
   - Open project in VS Code
   - Use F5 to start debugging session
   - Configure integration with real Jellyfin server

### Project Structure

```
uc-intg-jellyfin/
├── uc_intg_jellyfin/          # Main package
│   ├── __init__.py             # Package info  
│   ├── client.py               # Jellyfin API client
│   ├── config.py               # Configuration management
│   ├── driver.py               # Main integration driver
│   └── media_player.py         # Media player entity
├── .github/workflows/          # GitHub Actions CI/CD
│   └── build.yml               # Automated build pipeline
├── .git/hooks/                 # Git hooks for quality
│   └── pre-push                # Version consistency checking
├── docker-compose.yml          # Docker deployment
├── Dockerfile                  # Container build instructions
├── docker-entry.sh             # Container entry point
├── driver.json                 # Integration metadata
├── requirements.txt            # Dependencies
├── pyproject.toml              # Python project config
└── README.md                   # This file
```

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with real Jellyfin server
python uc_intg_jellyfin/driver.py

# Configure integration with Jellyfin server details
# Start media playback on Jellyfin client for testing
```

### Development Features

#### **Authentication System**
Complete Jellyfin authentication using official client library:
- **Official Library**: Uses jellyfin-apiclient-python for compatibility
- **Secure Authentication**: Username/password authentication
- **Session Management**: Persistent authentication across requests
- **Token Handling**: Automatic access token management

#### **Connection Monitoring**
Production-ready health checks and reconnection:
- **Health Endpoint**: Continuous server connectivity monitoring
- **Automatic Reconnection**: Seamless recovery from network issues
- **Graceful Degradation**: Proper handling of server unavailability
- **State Management**: Maintains entity state across interruptions

#### **Session Discovery**
Intelligent Jellyfin session detection and management:
- **Real-time Discovery**: Automatic detection of active sessions
- **User Filtering**: Shows only sessions for authenticated user
- **Deduplication**: Prevents duplicate entities for same client
- **Dynamic Updates**: Refreshes session list automatically

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and test with real Jellyfin server
4. Test with multiple Jellyfin clients if available
5. Commit changes: git commit -m 'Add amazing feature'
6. Push to branch: git push origin feature/amazing-feature
7. Open a Pull Request

## Credits

- **Developer**: Meir Miyara
- **Naim Audio**: HTTP API specification and device support
- **Unfolded Circle**: Remote 2/3 integration framework (ucapi)
- **Community**: Testing and feedback from UC community

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-naim/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community** 

**Thank You**: Meir Miyara