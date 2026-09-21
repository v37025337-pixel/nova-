"""Opaque HTTPS bytes. Content type and file suffix never select a reader."""

from datetime import datetime, timezone
import hashlib
import time
import urllib.request

from nova_core.contracts import ContractError
from nova_next.network import public_url, Redirects, proxy_route
from .rawcodec import MAX_BYTES


def fetch(url, timeout=15):
    public_url(url)
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "NOVA/1.1 raw observation research",
                                                  "Accept-Encoding": "identity"})
    with urllib.request.build_opener(Redirects()).open(request, timeout=timeout) as response:
        public_url(response.url)
        if response.status != 200 or response.headers.get("Content-Encoding", "identity") != "identity":
            raise ContractError("unsupported opaque response")
        raw = bytearray()
        while len(raw) <= MAX_BYTES:
            if time.monotonic() - started > timeout:
                raise TimeoutError("opaque source acquisition deadline")
            part = response.read(min(16384, MAX_BYTES + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        if not raw or len(raw) > MAX_BYTES:
            raise ContractError("opaque response byte budget")
        return {"url": url, "final_url": response.url, "status": 200, "hex": raw.hex(),
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "received_at": datetime.now(timezone.utc).isoformat(), "transport": "stdlib_https",
                "dns_policy": "configured_proxy" if proxy_route(url) else "local_public_resolution"}
