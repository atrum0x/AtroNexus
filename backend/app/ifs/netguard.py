"""Keeps IFS calls on the public internet (protection against SSRF).

Customers type their own IFS addresses. Without this check, someone could
enter an internal address (localhost, a private network, or the cloud
metadata service at 169.254.169.254) and make the backend call it for them.

Every URL is checked when a connection is saved (for a clear error) and again
right before every request (the name could resolve differently later). The
client doesn't follow redirects, so a public server can't bounce a request
inward.

Known gap: the check resolves the name, then httpx resolves it again to
connect. A DNS server that answers differently within that moment (DNS
rebinding) could slip through. Closing it needs connecting to the checked IP
directly; worth doing before handling untrusted traffic at scale.
"""

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from app.config import get_settings


class BlockedAddress(ValueError):
    """The URL isn't allowed. The message is meant for the user."""


def _system_resolve(host: str, port: int) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


# Tests replace this so they don't depend on real DNS.
resolve: Callable[[str, int], list[str]] = _system_resolve


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:10.0.0.1 is really 10.0.0.1
    # is_global is False for loopback, private, link-local (incl. the
    # metadata service), shared/CGNAT, reserved and unspecified addresses.
    return not ip.is_global or ip.is_multicast


def check_url(url: str) -> None:
    """Raises BlockedAddress unless url is https and every address its host resolves to is public.

    ALLOW_PRIVATE_IFS_URLS=true switches the check off, for local development
    against a fake IFS on localhost. Never set it in production.
    """
    if get_settings().allow_private_ifs_urls:
        return
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise BlockedAddress("IFS addresses must start with https://.")
    host = parts.hostname
    if not host:
        raise BlockedAddress("The address has no host name.")
    try:
        port = parts.port or 443
    except ValueError as exc:
        raise BlockedAddress("The address has an invalid port.") from exc

    try:
        addresses = resolve(host, port)
    except (OSError, UnicodeError) as exc:
        raise BlockedAddress(f"Can't find {host}. Check the address.") from exc
    if not addresses:
        raise BlockedAddress(f"Can't find {host}. Check the address.")

    for raw in addresses:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])  # drop an IPv6 zone like %eth0
        if _is_internal(ip):
            raise BlockedAddress(
                f"{host} points to an internal network address ({ip}). "
                "AtroNexus only connects to IFS servers on the public internet."
            )
