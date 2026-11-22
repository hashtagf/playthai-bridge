"""Bounded retries; one caller and no delivery backlog. Never log payloads or tokens."""

import ipaddress
import time

import httpx

from .protocol import Caption


def lan_host(host: str) -> str:
    address = ipaddress.IPv4Address(host)
    allowed = any(
        address in ipaddress.ip_network(n)
        for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
    )
    if not allowed:
        raise ValueError("Target must be a literal private LAN IPv4 or loopback address")
    return str(address)


class Publisher:
    def __init__(self, host: str, token: str, port: int = 8765, client=None, sleep=time.sleep):
        if len(token) < 24:
            raise ValueError("Pairing token must contain at least 24 characters")
        self.url = f"http://{lan_host(host)}:{port}"
        self.client = client or httpx.Client(timeout=1.0, trust_env=False)
        self.token = token
        self.sleep = sleep

    def send(self, caption: Caption):
        for attempt in range(3):
            try:
                response = self.client.post(
                    self.url + "/v1/captions",
                    json=caption.payload(),
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if response.status_code in (401, 403):
                    raise RuntimeError("TV rejected pairing token or LAN access")
                if response.status_code < 500 and response.status_code != 429:
                    if not response.is_success:
                        raise RuntimeError(f"TV rejected caption (HTTP {response.status_code})")
                    return
            except httpx.TransportError:
                pass
            if attempt < 2:
                self.sleep(0.15 * 2**attempt)
        raise RuntimeError("TV unavailable after three bounded attempts")

    def close(self):
        self.client.close()
