from __future__ import annotations

import ipaddress
import logging
import re
import socket
import subprocess
from typing import cast
from typing import TypedDict

import psutil

from .base import PlatformBase

logger = logging.getLogger(__name__)


def _run_windows_subprocess(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        timeout=timeout,
        check=False,
    )


def parse_route_print_ipv4(output: str) -> list[dict[str, object]]:
    routes: list[dict[str, object]] = []
    in_ipv4_table = False
    in_active_routes = False
    ip_pat = r"\d{1,3}(?:\.\d{1,3}){3}"
    row_re = re.compile(
        rf"^\s*({ip_pat})\s+({ip_pat})\s+({ip_pat}|On-link)\s+({ip_pat})\s+(\d+)\s*$"
    )

    for raw in output.splitlines():
        line = raw.rstrip()
        if "IPv4 Route Table" in line:
            in_ipv4_table = True
            in_active_routes = False
            continue
        if in_ipv4_table and "IPv6 Route Table" in line:
            break
        if not in_ipv4_table:
            continue
        if "Active Routes:" in line:
            in_active_routes = True
            continue
        if not in_active_routes:
            continue
        if line.strip().startswith("Network Destination") or not line.strip():
            continue

        m = row_re.match(line)
        if not m:
            continue

        destination, mask, gateway, iface, metric_str = m.groups()
        routes.append(
            {
                "interface": iface,
                "destination": destination,
                "gateway": gateway,
                "metric": int(metric_str),
                "mask": mask,
                "is_default": destination == "0.0.0.0",
            }
        )
    return routes


def parse_netsh_wlan_interfaces(output: str) -> dict[str, object]:
    kv: dict[str, str] = {}
    for raw in output.splitlines():
        if " : " not in raw:
            continue
        key, value = raw.split(" : ", 1)
        kv[key.strip().lower()] = value.strip()

    state = kv.get("state", "")
    if state.lower() != "connected":
        return cast(dict[str, object], _default_wifi("Not connected"))

    signal_pct: int | None = None
    signal_raw = kv.get("signal", "")
    if signal_raw.endswith("%"):
        try:
            signal_pct = int(signal_raw[:-1].strip())
        except ValueError:
            signal_pct = None

    tx_rate: float | None = None
    try:
        tx_rate = float(kv.get("transmit rate (mbps)", ""))
    except ValueError:
        tx_rate = None

    channel: int | None = None
    try:
        channel = int(kv.get("channel", ""))
    except ValueError:
        channel = None

    dbm = (signal_pct / 2.0) - 100 if signal_pct is not None else None
    info: WifiInfo = {
        "ssid": kv.get("ssid") or None,
        "bssid": kv.get("bssid") or None,
        "frequency_mhz": None,
        "channel": channel,
        "signal_dbm": dbm,
        "quality_pct": signal_pct,
        "tx_bitrate_mbps": tx_rate,
        "interface": kv.get("name") or None,
        "error": None,
    }
    return cast(dict[str, object], info)


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
    metric: int
    mask: str
    is_default: bool


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


def _default_wifi(error: str) -> WifiInfo:
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


class WindowsPlatform(PlatformBase):
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
                if "loopback" in lowered:
                    iface_type = "loopback"
                elif any(k in lowered for k in ("wi-fi", "wifi", "wlan", "wireless")):
                    iface_type = "wifi"
                elif any(k in lowered for k in ("ethernet", "eth")):
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
            logger.exception("Failed to collect Windows interfaces")
            return []
        return cast(list[dict[str, object]], interfaces)

    def get_routes(self) -> list[dict[str, object]]:
        """Return route dicts with keys: interface, destination, gateway, metric, mask."""
        routes: list[RouteInfo] = []
        try:
            proc = _run_windows_subprocess(["route", "print", "-4"], timeout=5)
            if proc.returncode != 0:
                logger.error("route print failed: %s", proc.stderr.strip())
                return []
            parsed = parse_route_print_ipv4(proc.stdout)
            routes.extend(cast(list[RouteInfo], parsed))
        except subprocess.TimeoutExpired:
            logger.warning("Timed out collecting Windows routes")
            return []
        except Exception:
            logger.exception("Failed to collect Windows routes")
            return []
        return cast(list[dict[str, object]], routes)

    def get_wifi_info(self) -> dict[str, object]:
        """Return Wi-Fi dict keys: ssid, bssid, frequency_mhz, channel, signal_dbm, quality_pct, tx_bitrate_mbps, interface, error."""
        try:
            proc = _run_windows_subprocess(["netsh", "wlan", "show", "interfaces"], timeout=5)
            if proc.returncode != 0:
                return cast(dict[str, object], _default_wifi("Not connected"))
            return parse_netsh_wlan_interfaces(proc.stdout)
        except subprocess.TimeoutExpired:
            logger.warning("Timed out collecting Windows Wi-Fi info")
            return cast(dict[str, object], _default_wifi("Not connected"))
        except Exception:
            logger.exception("Failed to collect Windows Wi-Fi info")
            return cast(dict[str, object], _default_wifi("Not connected"))

    def get_open_ports(self) -> list[dict[str, object]]:
        """Return socket dicts keys: pid, process, proto, local_ip, local_port, remote_ip, remote_port, state."""
        ports: list[OpenPortInfo] = []
        try:
            for conn in psutil.net_connections(kind="inet"):
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
            logger.exception("Failed to collect Windows open ports")
            return []
        return cast(list[dict[str, object]], ports)

    def get_dns_servers(self) -> list[str]:
        """Return deduplicated DNS server IPs from ipconfig /all output."""
        servers: list[str] = []
        try:
            proc = _run_windows_subprocess(["ipconfig", "/all"], timeout=5)
            if proc.returncode != 0:
                return []

            collecting = False
            for raw in proc.stdout.splitlines():
                line = raw.rstrip("\r\n")
                if "DNS Servers" in line and ":" in line:
                    collecting = True
                    _, right = line.split(":", 1)
                    candidate = right.strip()
                    if candidate:
                        try:
                            ipaddress.ip_address(candidate)
                            servers.append(candidate)
                        except ValueError:
                            pass
                    continue

                if collecting:
                    stripped = line.strip()
                    if not stripped:
                        collecting = False
                        continue
                    try:
                        ipaddress.ip_address(stripped)
                        servers.append(stripped)
                        continue
                    except ValueError:
                        collecting = False

        except subprocess.TimeoutExpired:
            logger.warning("Timed out collecting Windows DNS servers")
            return []
        except Exception:
            logger.exception("Failed to collect Windows DNS servers")
            return []

        deduped: list[str] = []
        seen: set[str] = set()
        for ip in servers:
            if ip not in seen:
                seen.add(ip)
                deduped.append(ip)
        return deduped
