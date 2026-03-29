from __future__ import annotations

import asyncio
import logging
import time
from typing import TypedDict

import dns.exception
import dns.resolver

from netui import config

logger = logging.getLogger(__name__)


class DnsResolveResult(TypedDict):
    hostname: str
    ip_list: list[str]
    ttl: int
    query_time_ms: float
    resolver: str | None
    error: str | None


def _resolve_host_sync(hostname: str, resolver_ip: str | None = None) -> DnsResolveResult:
    resolver = dns.resolver.Resolver()
    if resolver_ip:
        resolver.nameservers = [resolver_ip]
    resolver_name = str(resolver.nameservers[0]) if resolver.nameservers else None

    start = time.monotonic()
    try:
        answer = resolver.resolve(hostname, "A")
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return {
            "hostname": hostname,
            "ip_list": [r.address for r in answer],
            "ttl": int(answer.rrset.ttl) if answer.rrset is not None else 0,
            "query_time_ms": elapsed_ms,
            "resolver": resolver_name,
            "error": None,
        }
    except dns.exception.DNSException as exc:
        return {
            "hostname": hostname,
            "ip_list": [],
            "ttl": 0,
            "query_time_ms": 0.0,
            "resolver": resolver_name,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Unexpected DNS resolver error for %s", hostname)
        return {
            "hostname": hostname,
            "ip_list": [],
            "ttl": 0,
            "query_time_ms": 0.0,
            "resolver": resolver_name,
            "error": str(exc),
        }


async def resolve_host(hostname: str, resolver_ip: str | None = None) -> DnsResolveResult:
    """Return DNS dict keys: hostname, ip_list, ttl, query_time_ms, resolver, error."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _resolve_host_sync, hostname, resolver_ip)


async def bulk_resolve(hosts: list[str] | None = None) -> list[DnsResolveResult]:
    """Resolve many hosts concurrently and sort by query_time_ms ascending."""
    target_hosts = hosts or config.DEFAULT_DNS_TEST_HOSTS
    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, _resolve_host_sync, host, None) for host in target_hosts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    clean: list[DnsResolveResult] = []
    for item in results:
        if isinstance(item, BaseException):
            logger.exception("bulk_resolve worker failed", exc_info=item)
            continue
        clean.append(item)
    return sorted(clean, key=lambda r: r["query_time_ms"])


async def collect() -> list[DnsResolveResult]:
    return await bulk_resolve()
