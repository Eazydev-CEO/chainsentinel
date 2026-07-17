"""SSRF protection for outbound webhook deliveries.

Blocks: localhost & loopback, RFC1918/private ranges, link-local, cloud
metadata endpoints, non-http(s) schemes, unusual ports, credential-bearing
URLs. Hostnames are DNS-resolved and every resolved address must be public.
Redirects are never followed (enforced at request time).
"""
import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings


class WebhookSecurityError(Exception):
    """URL failed SSRF validation."""


BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",  # AWS legacy
    "metadata.azure.com",
    "metadata.platformequinix.com",
}

METADATA_IPS = {
    "169.254.169.254",  # AWS/GCP/Azure/OpenStack metadata
    "100.100.100.200",  # Alibaba Cloud metadata
    "192.0.0.192",  # Oracle Cloud legacy
}


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    if str(ip) in METADATA_IPS:
        return "cloud metadata endpoint"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_private:
        return "private network address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_reserved:
        return "reserved address"
    if ip.is_unspecified:
        return "unspecified address"
    # IPv4-mapped IPv6 (::ffff:10.0.0.1) — check the embedded IPv4 too.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    return None


def validate_webhook_url(url: str, *, resolve: bool = True) -> list[str]:
    """Validate a destination URL. Returns the resolved public IPs.

    Raises WebhookSecurityError with a user-safe message on any violation.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:
        raise WebhookSecurityError("URL could not be parsed.") from exc

    if parts.scheme not in ("http", "https"):
        raise WebhookSecurityError("Only http:// and https:// destinations are allowed.")
    if not parts.hostname:
        raise WebhookSecurityError("URL has no hostname.")
    if parts.username or parts.password:
        raise WebhookSecurityError("URLs with embedded credentials are not allowed.")

    hostname = parts.hostname.lower().rstrip(".")
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise WebhookSecurityError("Destination host is not allowed.")

    port = parts.port or (443 if parts.scheme == "https" else 80)
    allowed_ports = settings.WEBHOOK_ALLOWED_PORTS
    if allowed_ports and port not in allowed_ports:
        raise WebhookSecurityError(
            f"Port {port} is not allowed. Allowed ports: "
            f"{', '.join(str(p) for p in allowed_ports)}."
        )

    # IP-literal host?
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
    if ip is not None:
        reason = _is_blocked_ip(ip)
        if reason:
            raise WebhookSecurityError(f"Destination resolves to a {reason}.")
        return [str(ip)]

    if not resolve:
        return []

    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebhookSecurityError("Destination hostname does not resolve.") from exc

    resolved: list[str] = []
    for info in infos:
        address = info[4][0]
        try:
            candidate = ipaddress.ip_address(address)
        except ValueError:
            continue
        reason = _is_blocked_ip(candidate)
        if reason:
            raise WebhookSecurityError(f"Destination resolves to a {reason}.")
        resolved.append(address)

    if not resolved:
        raise WebhookSecurityError("Destination hostname did not resolve to a usable address.")
    return resolved
