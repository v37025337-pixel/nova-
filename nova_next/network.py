"""Bounded public HTTPS acquisition with complete capture and provenance."""

from datetime import datetime, timezone
import hashlib
import ipaddress
import socket
import time
from urllib.parse import urlsplit
import urllib.request

from nova_core.contracts import ContractError
from .data import MAX_BYTES


def proxy_route(url):
    # urllib delegates origin DNS to the explicitly configured HTTPS proxy.
    # Never expose proxy URLs/credentials in receipts or diagnostics.
    return bool(urllib.request.getproxies().get("https")
                and not urllib.request.proxy_bypass(urlsplit(url).hostname))


def public_url(url, resolve=True):
    if type(url) is not str or len(url) > 2048:
        raise ContractError("invalid URL")
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.username or p.password or
            p.port not in (None, 443) or p.fragment or any(ord(c) < 32 for c in url)):
        raise ContractError("source must be a credential-free public HTTPS URL")
    if p.hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ContractError("local destination")
    try:
        literal = ipaddress.ip_address(p.hostname)
    except ValueError:
        literal = None
    if literal and not literal.is_global:
        raise ContractError("non-public destination")
    if resolve and not proxy_route(url):
        answers = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
            raise ContractError("DNS resolves to a non-public destination")
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, timeout=15):
    public_url(url)
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "Nova-Next/0.1 (public source research)",
                                                  "Accept-Encoding": "identity"})
    opener = urllib.request.build_opener(Redirects())
    with opener.open(request, timeout=timeout) as response:
        public_url(response.url)
        if response.status != 200 or response.headers.get("Content-Encoding", "identity") != "identity":
            raise ContractError("unsupported response or content encoding")
        raw = bytearray()
        while len(raw) <= MAX_BYTES:
            if time.monotonic() - started > timeout:
                raise TimeoutError("total source acquisition deadline")
            part = response.read(min(16384, MAX_BYTES + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        if not raw or len(raw) > MAX_BYTES:
            raise ContractError("source response outside byte budget")
        text = bytes(raw).decode("utf-8")
        return {"url": url, "final_url": response.url, "status": response.status,
                "text": text, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "content_type": response.headers.get("Content-Type", ""),
                "etag": response.headers.get("ETag", ""),
                "received_at": datetime.now(timezone.utc).isoformat(), "transport": "stdlib_https",
                "seconds": time.monotonic() - started,
                "dns_policy": "configured_proxy" if proxy_route(url) else "local_public_resolution"}
