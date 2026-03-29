from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dns.exception as dns_exception
import pytest

from netui.collectors import dns, latency, traceroute
from netui.collectors.dns import DnsResolveResult
from netui.collectors.latency import PingResult
from netui.platforms.linux import parse_proc_net_route
from netui.platforms.windows import parse_netsh_wlan_interfaces, parse_route_print_ipv4
from netui.utils.formatters import (
    bits_per_sec_to_human,
    bytes_to_human,
    ms_to_colored_str,
    ms_to_str,
    pct_to_colored_str,
)
from netui.utils.history import RollingHistory
from netui.utils.sparkline import render_sparkline

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFormatters:
    def test_bytes_to_human(self) -> None:
        assert bytes_to_human(-5) == "0 B"
        assert bytes_to_human(1023) == "1023 B"
        assert bytes_to_human(1024) == "1.0 KB"
        assert bytes_to_human(1024 * 1024) == "1.0 MB"

    def test_ms_formatters(self) -> None:
        assert ms_to_str(12.345) == "12.3 ms"
        assert ms_to_colored_str(20).startswith("[green]")
        assert ms_to_colored_str(80).startswith("[yellow]")
        assert ms_to_colored_str(180).startswith("[red]")

    def test_pct_colored(self) -> None:
        assert pct_to_colored_str(0.2).startswith("[green]")
        assert pct_to_colored_str(2.0).startswith("[yellow]")
        assert pct_to_colored_str(10.0).startswith("[red]")

    def test_bits_per_sec_to_human(self) -> None:
        assert bits_per_sec_to_human(-1) == "0 bps"
        assert bits_per_sec_to_human(999) == "999 bps"
        assert bits_per_sec_to_human(12_500) == "12.50 Kbps"
        assert bits_per_sec_to_human(3_400_000) == "3.40 Mbps"


class TestRollingHistory:
    def test_push_and_windowing(self) -> None:
        h = RollingHistory(maxlen=3)
        h.push(1)
        h.push(2)
        h.push(3)
        h.push(4)
        assert h.get_all() == [2, 3, 4]
        assert h.get_last_n(2) == [3, 4]

    def test_stats_empty_and_values(self) -> None:
        h = RollingHistory()
        assert h.average() == 0.0
        assert h.min() == 0.0
        assert h.max() == 0.0
        h.push(10)
        h.push(30)
        assert h.average() == 20.0
        assert h.min() == 10
        assert h.max() == 30


class TestSparkline:
    def test_empty_values(self) -> None:
        s = render_sparkline([], width=5)
        assert len(s) == 5

    def test_constant_values(self) -> None:
        s = render_sparkline([7, 7, 7], width=6)
        assert len(set(s)) == 1
        assert len(s) == 6

    def test_sample_and_pad(self) -> None:
        assert len(render_sparkline([1, 2, 3, 4, 5, 6], width=4)) == 4
        assert len(render_sparkline([1, 3], width=6)) == 6


class TestWindowsParsers:
    @pytest.mark.parametrize(
        "fixture_name, expected_ssid, expected_channel",
        [
            ("netsh_wlan_win10.txt", "HomeNet", 36),
            ("netsh_wlan_win11.txt", "Office5G", 149),
        ],
    )
    def test_parse_netsh_wlan_interfaces(
        self,
        fixture_name: str,
        expected_ssid: str,
        expected_channel: int,
    ) -> None:
        output = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
        parsed = parse_netsh_wlan_interfaces(output)
        assert parsed["error"] is None
        assert parsed["ssid"] == expected_ssid
        assert parsed["channel"] == expected_channel
        assert isinstance(parsed["quality_pct"], int)

    @pytest.mark.parametrize(
        "fixture_name, expected_gateway",
        [
            ("route_print_win10.txt", "192.168.1.1"),
            ("route_print_win11.txt", "10.10.0.1"),
        ],
    )
    def test_parse_route_print_ipv4(self, fixture_name: str, expected_gateway: str) -> None:
        output = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
        routes = parse_route_print_ipv4(output)
        assert routes
        default_route = next(r for r in routes if bool(r["is_default"]))
        assert default_route["gateway"] == expected_gateway
        assert default_route["destination"] == "0.0.0.0"


class TestLinuxParsers:
    def test_parse_proc_net_route(self) -> None:
        sample = """Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT
eth0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0
eth0\t0001A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0
"""
        routes = parse_proc_net_route(sample)
        assert len(routes) == 2
        assert routes[0]["destination"] == "0.0.0.0"
        assert routes[0]["gateway"] == "192.168.1.1"
        assert routes[1]["mask"] == "255.255.255.0"


class TestTracerouteParsers:
    def test_parse_windows_tracert_line(self) -> None:
        parsed = traceroute.parse_tracert_windows_line(
            "  3    15 ms    18 ms    14 ms  203.0.113.5"
        )
        assert parsed is not None
        assert parsed["hop_num"] == 3
        assert parsed["ip"] == "203.0.113.5"
        assert parsed["is_timeout"] is False

    def test_parse_windows_timeout_line(self) -> None:
        parsed = traceroute.parse_tracert_windows_line("  4     *        *        *     Request timed out.")
        assert parsed is not None
        assert parsed["is_timeout"] is True

    def test_parse_linux_traceroute_line(self) -> None:
        parsed = traceroute.parse_traceroute_linux_line(" 2  10.0.0.1  12.345 ms  11.234 ms  10.999 ms")
        assert parsed is not None
        assert parsed["hop_num"] == 2
        assert parsed["ip"] == "10.0.0.1"
        assert abs(parsed["latency_ms"] - 12.345) < 1e-6

    def test_parse_linux_timeout_line(self) -> None:
        parsed = traceroute.parse_traceroute_linux_line(" 5  * * *")
        assert parsed is not None
        assert parsed["is_timeout"] is True


class TestLatencyCollector:
    def test_parse_ping_avg_ms(self) -> None:
        linux = "rtt min/avg/max/mdev = 12.345/34.567/56.789/1.0 ms"
        windows = "Approximate round trip times in milli-seconds:\n    Minimum = 10ms, Maximum = 30ms, Average = 20ms"
        assert abs(latency._parse_ping_avg_ms(linux) - 34.567) < 1e-6  # pyright: ignore[reportPrivateUsage]
        assert latency._parse_ping_avg_ms(windows) == 20.0  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_permission_error_switches_to_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_subprocess_ping(host: str, count: int = 1) -> PingResult:
            return {
                "host": host,
                "avg_ms": 11.0,
                "min_ms": 10.0,
                "max_ms": 12.0,
                "jitter_ms": 2.0,
                "packet_loss_pct": 0.0,
                "is_alive": True,
                "fallback_mode": True,
            }

        async def raising_async_ping(*args: Any, **kwargs: Any) -> None:
            raise PermissionError("raw socket denied")

        monkeypatch.setattr(latency, "_icmp_probed", True)
        monkeypatch.setattr(latency, "icmp_fallback_mode", False)
        monkeypatch.setattr(latency, "async_ping", raising_async_ping)
        monkeypatch.setattr(latency, "_subprocess_ping", fake_subprocess_ping)

        result = await latency.ping_host("8.8.8.8", count=1)
        assert result["fallback_mode"] is True
        assert latency.icmp_fallback_mode is True


class TestDnsCollector:
    def test_resolve_host_sync_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeAnswer:
            rrset = SimpleNamespace(ttl=60)

            def __iter__(self):
                return iter([SimpleNamespace(address="1.1.1.1"), SimpleNamespace(address="8.8.8.8")])

        class FakeResolver:
            def __init__(self) -> None:
                self.nameservers = ["9.9.9.9"]

            def resolve(self, hostname: str, kind: str):
                assert hostname == "example.com"
                assert kind == "A"
                return FakeAnswer()

        monkeypatch.setattr(dns.dns.resolver, "Resolver", FakeResolver)
        result = dns._resolve_host_sync("example.com")  # pyright: ignore[reportPrivateUsage]
        assert result["error"] is None
        assert result["ip_list"] == ["1.1.1.1", "8.8.8.8"]
        assert result["ttl"] == 60

    def test_resolve_host_sync_dns_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResolver:
            def __init__(self) -> None:
                self.nameservers = ["1.1.1.1"]

            def resolve(self, hostname: str, kind: str):
                raise dns_exception.Timeout()

        monkeypatch.setattr(dns.dns.resolver, "Resolver", FakeResolver)
        result = dns._resolve_host_sync("bad.example")  # pyright: ignore[reportPrivateUsage]
        assert result["ip_list"] == []
        assert result["ttl"] == 0
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_bulk_resolve_sorts_and_filters_exceptions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mapping: dict[str, DnsResolveResult] = {
            "fast.example": {
                "hostname": "fast.example",
                "ip_list": ["1.1.1.1"],
                "ttl": 30,
                "query_time_ms": 5.0,
                "resolver": "1.1.1.1",
                "error": None,
            },
            "slow.example": {
                "hostname": "slow.example",
                "ip_list": ["8.8.8.8"],
                "ttl": 30,
                "query_time_ms": 25.0,
                "resolver": "1.1.1.1",
                "error": None,
            },
        }

        def fake_resolve(host: str, resolver_ip: str | None = None) -> DnsResolveResult:
            if host == "boom.example":
                raise RuntimeError("boom")
            return mapping[host]

        monkeypatch.setattr(dns, "_resolve_host_sync", fake_resolve)
        results = await dns.bulk_resolve(["slow.example", "boom.example", "fast.example"])
        assert [r["hostname"] for r in results] == ["fast.example", "slow.example"]


@pytest.mark.asyncio
async def test_collectors_return_data_shapes() -> None:
    ping = await latency.ping_host("127.0.0.1", count=1)
    assert set(ping.keys()) == {
        "host",
        "avg_ms",
        "min_ms",
        "max_ms",
        "jitter_ms",
        "packet_loss_pct",
        "is_alive",
        "fallback_mode",
    }

    resolved = await dns.resolve_host("localhost")
    assert set(resolved.keys()) == {
        "hostname",
        "ip_list",
        "ttl",
        "query_time_ms",
        "resolver",
        "error",
    }
