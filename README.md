# NetUI — Network Diagnostics TUI

A terminal user interface for real-time network diagnostics,
inspired by lazydocker. Built with Python + Textual.

## Features
- Live ping latency with sparkline history
- Download/upload speed test (no external service required)
- DNS resolution timing and bulk lookup
- Hop-by-hop traceroute with live streaming
- Real-time bandwidth monitor (per interface, per second)
- Open ports and listening services
- Wi-Fi signal strength and details
- Routing table viewer
- Works on Linux (Ubuntu 20.04+) and Windows 11

## Installation

### Install via Git
```bash
git clone https://github.com/Surya-T-S/netui.git
cd netui
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m netui
```

### Update after new GitHub changes
```bash
cd netui
git pull origin main
source .venv/bin/activate
pip install -e ".[dev]" --upgrade
python -m netui
```

### Install directly from GitHub (no clone)
```bash
pip install "git+https://github.com/Surya-T-S/netui.git"
netui
```

### Install a stable tagged release
```bash
pip install "git+https://github.com/Surya-T-S/netui.git@v0.1.1"
```

### Linux
```bash
pip install netui
netui
# For full ICMP support (no sudo required after this):
sudo setcap cap_net_raw+ep $(which python3)
```

### Windows
```powershell
pip install netui
# Run as Administrator for full ICMP support:
netui
# Or run normally for limited mode (subprocess ping fallback):
netui
```

### From source
```bash
git clone https://github.com/Surya-T-S/netui.git
cd netui
pip install -e ".[dev]"
python -m netui
```

## Keyboard Reference
```text
q              Quit
Tab            Cycle sidebar sections
↑ / ↓          Navigate
r              Refresh panel
?              Help screen
s              Start speed test (Speed panel)
t              Run traceroute (Traceroute panel)
i              Cycle interface (Bandwidth panel)
/              Filter (DNS / Ports panels)
c              Cycle color theme
Esc            Cancel / close
Ctrl+L         Reset panel
```

## Requirements
- Python 3.11+
- Linux: iw or iwconfig for Wi-Fi info
- Windows: Run as Administrator for ICMP raw sockets

## Troubleshooting
- "Permission denied" on ping: run as root or set cap_net_raw (Linux)
- Wi-Fi panel empty: install iw (sudo apt install iw)
- Speed test slow: ensure no VPN is active during test
- Windows: run as Administrator for full ICMP functionality

OPTIONAL: Build standalone executable with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile \
	--name netui \
	--add-data "netui/netui.tcss:netui" \
	--hidden-import textual \
	--hidden-import psutil \
	--hidden-import icmplib \
	--hidden-import dns \
	netui/main.py
```

Output: dist/netui (Linux) or dist/netui.exe (Windows)
Distribute the single file — no Python installation required.

Create netui.spec if PyInstaller one-file has issues finding Textual CSS:
Add to Analysis.datas:
- ("netui/netui.tcss", "netui"),
- ("netui/widgets/*.tcss", "netui/widgets") if any widget CSS files exist
