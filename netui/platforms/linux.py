from __future__ import annotations

import ipaddress
import logging
import os
import re
import shutil
import socket
import struct
import subprocess
from typing import cast
from typing import TypedDict

import psutil

from .base import PlatformBase

logger = logging.getLogger(__name__)


class InterfaceInfo(TypedDict):
    name: str
    ipv4: str | None
    ipv6: str | None
    mac: str | None
    mtu: int
    speed_mbps: int
    is_up: bool
    type: str


class RouteInfo(TypedDict):
    interface: str
    destination: str
    gateway: str
    flags: int
    metric: int
    mask: str


class WifiInfo(TypedDict):
    ssid: str | None
    bssid: str | None
    frequency_mhz: int | None
    channel: int | None
    signal_dbm: float | None
    quality_pct: int | None
    tx_bitrate_mbps: float | None
    interface: str | None
    error: str | None


class OpenPortInfo(TypedDict):
    pid: int | None
    process: str
    proto: str
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    state: str


def _default_wifi(error: str | None) -> WifiInfo:
    return {
        "ssid": None,
        "bssid": None,
        "frequency_mhz": None,
        "channel": None,
        "signal_dbm": None,
        "quality_pct": None,
        "tx_bitrate_mbps": None,
        "interface": None,
        "error": error,
    }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _freq_to_channel(freq_mhz: int | None) -> int | None:
    if freq_mhz is None:
        return None
    if 2412 <= freq_mhz <= 2484:
        if freq_mhz == 2484:
            return 14
        return (freq_mhz - 2407) // 5
    if 5000 <= freq_mhz <= 5900:
        return (freq_mhz - 5000) // 5
    if 5955 <= freq_mhz <= 7115:
        return (freq_mhz - 5950) // 5
    return None


def _route_hex_to_ip(hex_str: str) -> str:
    return socket.inet_ntoa(struct.pack("<I", int(hex_str, 16)))


def parse_proc_net_route(content: str) -> list[dict[str, object]]:
    routes: list[dict[str, object]] = []
    for line_num, line in enumerate(content.splitlines()):
        if line_num == 0:
            continue
        cols = line.split()
        if len(cols) < 11:
            continue
        iface, destination_hex, gateway_hex, flags_hex = (
            cols[0],
            cols[1],
            cols[2],
            cols[3],
        )
        metric_str = cols[6]
        mask_hex = cols[7]

        destination = _route_hex_to_ip(destination_hex)
        gateway = _route_hex_to_ip(gateway_hex)
        mask = _route_hex_to_ip(mask_hex)
        flags = int(flags_hex, 16)
        metric = int(metric_str)

        if destination == "0.0.0.0":
            flags |= 0x0003

        routes.append(
            {
                "interface": iface,
                "destination": destination,
                "gateway": gateway,
                "flags": flags,
                "metric": metric,
                "mask": mask,
            }
        )
    return routes


def _iface_type_from_sysfs(name: str) -> str | None:
    path = f"/sys/class/net/{name}/type"
    if not os.path.exists(path):
        return None
    try:
        code = int(open(path, "r", encoding="utf-8").read().strip())
    except Exception:
        return None
    if code == 1:
        return "ethernet"
    if code == 772:
        return "loopback"
    if code == 801:
        return "wifi"
    return None


class LinuxPlatform(PlatformBase):
    def get_interfaces(self) -> list[dict[str, object]]:
        """Return interface dicts with keys: name, ipv4, ipv6, mac, mtu, speed_mbps, is_up, type."""
        interfaces: list[InterfaceInfo] = []
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, addr_list in addrs.items():
                ipv4: str | None = None
                ipv6: str | None = None
                mac: str | None = None
                for addr in addr_list:
                    if addr.family == socket.AF_INET and not ipv4:
                        ipv4 = addr.address
                    elif addr.family == socket.AF_INET6 and not ipv6:
                        ipv6 = addr.address.split("%", 1)[0]
                    elif getattr(psutil, "AF_LINK", object()) == addr.family and not mac:
                        mac = addr.address

                st = stats.get(name)
                speed_mbps = int(st.speed) if st and st.speed >= 0 else 0
                mtu = int(st.mtu) if st else 0
                is_up = bool(st.isup) if st else False

                lowered = name.lower()
                sys_type = _iface_type_from_sysfs(name)
                if sys_type:
                    iface_type = sys_type
                elif lowered == "lo" or lowered.startswith("lo"):
                    iface_type = "loopback"
                elif lowered.startswith("w") or lowered.startswith("wl"):
                    iface_type = "wifi"
                elif lowered.startswith(("eth", "en", "eno", "ens", "enp")):
                    iface_type = "ethernet"
                else:
                    iface_type = "unknown"

                interfaces.append(
                    {
                        "name": name,
                        "ipv4": ipv4,
                        "ipv6": ipv6,
                        "mac": mac,
                        "mtu": mtu,
                        "speed_mbps": speed_mbps,
                        "is_up": is_up,
                        "type": iface_type,
                    }
                )
        except Exception:
            logger.exception("Failed to collect Linux interfaces")
            return []
        return cast(list[dict[str, object]], interfaces)

    def get_routes(self) -> list[dict[str, object]]:
        """Return route dicts with keys: interface, destination, gateway, flags, metric, mask."""
        routes: list[RouteInfo] = []
        if not os.path.exists("/proc/net/route"):
            logger.warning("/proc/net/route does not exist")
            return []
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                routes.extend(cast(list[RouteInfo], parse_proc_net_route(f.read())))
        except Exception:
            logger.exception("Failed to collect Linux routes")
            return []
        return cast(list[dict[str, object]], routes)

    def get_wifi_info(self) -> dict[str, object]:
        """Return Wi-Fi dict keys: ssid, bssid, frequency_mhz, channel, signal_dbm, quality_pct, tx_bitrate_mbps, interface, error."""
        iw_path = shutil.which("iw")
        iwconfig_path = shutil.which("iwconfig")
        if not iw_path and not iwconfig_path:
            return cast(
                dict[str, object],
                _default_wifi(
                    "Neither iw nor iwconfig found. Install iw: sudo apt install iw"
                ),
            )

        try:
            if iw_path:
                logger.info("Using iw for Wi-Fi info")
                return self._wifi_from_iw()
        except Exception:
            logger.exception("Failed to collect Wi-Fi info with iw")

        try:
            logger.info("Using iwconfig for Wi-Fi info")
            return self._wifi_from_iwconfig()
        except Exception as exc:
            logger.exception("Failed to collect Wi-Fi info with iwconfig")
            return cast(dict[str, object], _default_wifi(str(exc)))

    def _wifi_from_iw(self) -> dict[str, object]:
        dev = subprocess.run(
            ["iw", "dev"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if dev.returncode != 0:
            return cast(dict[str, object], _default_wifi(dev.stderr.strip() or "iw dev failed"))

        iface: str | None = None
        for line in dev.stdout.splitlines():
            m = re.search(r"^\s*Interface\s+(\S+)", line)
            if m:
                iface = m.group(1)
                break
        if not iface:
            return cast(dict[str, object], _default_wifi("No Wi-Fi interface found"))

        link = subprocess.run(
            ["iw", "dev", iface, "link"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if link.returncode != 0:
            return cast(dict[str, object], _default_wifi(link.stderr.strip() or "iw link failed"))

        station = subprocess.run(
            ["iw", "dev", iface, "station", "dump"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        info: WifiInfo = _default_wifi(None)
        info["interface"] = iface

        for line in link.stdout.splitlines():
            line = line.strip()
            if line.startswith("Connected to "):
                info["bssid"] = line.replace("Connected to ", "", 1).strip()
            elif line.startswith("SSID:"):
                info["ssid"] = line.split(":", 1)[1].strip() or None
            elif line.startswith("freq:"):
                m_freq = re.search(r"(\d+)", line)
                if m_freq:
                    freq = int(m_freq.group(1))
                    info["frequency_mhz"] = freq
                    info["channel"] = _freq_to_channel(freq)
            elif line.startswith("signal:"):
                m_sig = re.search(r"(-?\d+(?:\.\d+)?)", line)
                if m_sig:
                    dbm = float(m_sig.group(1))
                    info["signal_dbm"] = dbm
                    info["quality_pct"] = int(_clamp(2 * (dbm + 100), 0, 100))
            elif line.startswith("tx bitrate:"):
                m_rate = re.search(r"(\d+(?:\.\d+)?)", line)
                if m_rate:
                    info["tx_bitrate_mbps"] = float(m_rate.group(1))

        if station.returncode == 0:
            rx_bytes: int | None = None
            tx_bytes: int | None = None
            inactive_time_ms: int | None = None
            for station_line in station.stdout.splitlines():
                s = station_line.strip()
                if s.startswith("rx bytes:"):
                    m_rx = re.search(r"(\d+)", s)
                    if m_rx:
                        rx_bytes = int(m_rx.group(1))
                elif s.startswith("tx bytes:"):
                    m_tx = re.search(r"(\d+)", s)
                    if m_tx:
                        tx_bytes = int(m_tx.group(1))
                elif s.startswith("inactive time:"):
                    m_inactive = re.search(r"(\d+)", s)
                    if m_inactive:
                        inactive_time_ms = int(m_inactive.group(1))
            _ = (rx_bytes, tx_bytes, inactive_time_ms)

        if info["ssid"] is None:
            info["error"] = "Not connected"
        return cast(dict[str, object], info)

    def _wifi_from_iwconfig(self) -> dict[str, object]:
        run = subprocess.run(
            ["iwconfig"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if run.returncode != 0:
            return cast(dict[str, object], _default_wifi(run.stderr.strip() or "iwconfig failed"))

        info: WifiInfo = _default_wifi(None)
        current_iface: str | None = None

        for raw in run.stdout.splitlines():
            line = raw.rstrip()
            iface_match = re.match(r"^(\S+)\s+IEEE", line)
            if iface_match:
                current_iface = iface_match.group(1)
                info["interface"] = current_iface

            if "ESSID:" in line:
                ssid_match = re.search(r'ESSID:"([^"]*)"', line)
                if ssid_match:
                    ssid = ssid_match.group(1).strip()
                    info["ssid"] = ssid if ssid and ssid.lower() != "off/any" else None

            if "Access Point:" in line:
                ap_match = re.search(r"Access Point:\s*([0-9A-Fa-f:]{17}|Not-Associated)", line)
                if ap_match:
                    bssid = ap_match.group(1)
                    info["bssid"] = None if bssid == "Not-Associated" else bssid

            if "Frequency:" in line:
                mhz_match = re.search(r"Frequency:([0-9.]+)\s*GHz", line)
                if mhz_match:
                    mhz = int(float(mhz_match.group(1)) * 1000)
                    info["frequency_mhz"] = mhz
                    info["channel"] = _freq_to_channel(mhz)

            if "Signal level=" in line:
                sig_match = re.search(r"Signal level=([-0-9.]+)\s*dBm", line)
                if sig_match:
                    dbm = float(sig_match.group(1))
                    info["signal_dbm"] = dbm
                    info["quality_pct"] = int(_clamp(2 * (dbm + 100), 0, 100))

            if "Bit Rate=" in line:
                rate_match = re.search(r"Bit Rate=([0-9.]+)\s*Mb/s", line)
                if rate_match:
                    info["tx_bitrate_mbps"] = float(rate_match.group(1))

        if not info["ssid"]:
            info["error"] = "Not connected"
        return cast(dict[str, object], info)

    def get_open_ports(self) -> list[dict[str, object]]:
        """Return socket dicts keys: pid, process, proto, local_ip, local_port, remote_ip, remote_port, state."""
        ports: list[OpenPortInfo] = []
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                pid = conn.pid
                process_name = "<unknown>"
                if pid is not None:
                    try:
                        process_name = psutil.Process(pid).name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pid = None
                        process_name = "<unknown>"

                proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
                local_ip = conn.laddr.ip if conn.laddr else ""
                local_port = conn.laddr.port if conn.laddr else 0
                remote_ip = conn.raddr.ip if conn.raddr else ""
                remote_port = conn.raddr.port if conn.raddr else 0

                ports.append(
                    {
                        "pid": pid,
                        "process": process_name,
                        "proto": proto,
                        "local_ip": local_ip,
                        "local_port": local_port,
                        "remote_ip": remote_ip,
                        "remote_port": remote_port,
                        "state": conn.status or "NONE",
                    }
                )
        except Exception:
            logger.exception("Failed to collect Linux open ports")
            return []
        return cast(list[dict[str, object]], ports)

    def get_dns_servers(self) -> list[str]:
        """Return DNS server IP addresses from resolved/resolv.conf sources."""
        servers: list[str] = []

        candidate_paths = [
            "/run/systemd/resolve/resolv.conf",
            "/etc/resolv.conf",
            "/etc/resolvconf/run/resolv.conf",
        ]

        def _parse_resolv_file(path: str) -> list[str]:
            parsed: list[str] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped.startswith("nameserver"):
                        continue
                    parts = stripped.split()
                    if len(parts) < 2:
                        continue
                    ip = parts[1]
                    try:
                        ipaddress.ip_address(ip)
                        parsed.append(ip)
                    except ValueError:
                        continue
            return parsed

        try:
            for path in candidate_paths:
                if os.path.exists(path):
                    servers.extend(_parse_resolv_file(path))
                    if servers:
                        return list(dict.fromkeys(servers))

            try:
                proc = subprocess.run(
                    ["resolvectl", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        m = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", line)
                        if m:
                            ip = m.group(1)
                            try:
                                ipaddress.ip_address(ip)
                                servers.append(ip)
                            except ValueError:
                                continue
            except subprocess.TimeoutExpired:
                logger.warning("resolvectl status timed out")
        except Exception:
            logger.exception("Failed to collect Linux DNS servers")
            return []
        return list(dict.fromkeys(servers))
