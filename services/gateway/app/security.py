from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException, Request, WebSocket

AUTH_MODE_ENV = "OPENCOMMOTION_AUTH_MODE"
API_KEYS_ENV = "OPENCOMMOTION_API_KEYS"
ALLOWED_IPS_ENV = "OPENCOMMOTION_ALLOWED_IPS"

EXEMPT_PATH_EXACT = {
    "/",
    "/index.html",
    "/favicon.ico",
    "/robots.txt",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
    "/v1/runtime/capabilities",
    "/v1/voice/capabilities",
    "/v2/runtime/capabilities",
}
EXEMPT_PATH_PREFIXES = {
    "/assets/",
}


@dataclass
class SecurityState:
    mode: str
    api_keys: set[str]
    allowed_ips: list[str]

    @property
    def enforcement_active(self) -> bool:
        if self.mode == "api-key":
            return bool(self.api_keys)
        if self.mode == "network-trust":
            return bool(self.allowed_ips)
        return False


def get_security_state() -> SecurityState:
    mode = os.getenv(AUTH_MODE_ENV, "api-key").strip().lower()
    if mode not in {"api-key", "network-trust"}:
        mode = "api-key"
    keys_raw = os.getenv(API_KEYS_ENV, "").strip()
    api_keys = {row.strip() for row in keys_raw.split(",") if row.strip()}
    allowed_raw = os.getenv(ALLOWED_IPS_ENV, "").strip()
    allowed_ips = [row.strip() for row in allowed_raw.split(",") if row.strip()]
    return SecurityState(mode=mode, api_keys=api_keys, allowed_ips=allowed_ips)


def path_is_exempt(path: str) -> bool:
    if path in EXEMPT_PATH_EXACT:
        return True
    for prefix in EXEMPT_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    if path.startswith("/v1/audio/"):
        return True
    if path.startswith("/v1/setup/"):
        return True
    return False


def _extract_api_key(header_values: Iterable[str], auth_header: str | None) -> str:
    for value in header_values:
        if value.strip():
            return value.strip()
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _host_allowed(host: str | None, allowed: list[str]) -> bool:
    if host is None:
        return False
    if not allowed:
        return True
    if host in allowed:
        return True
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        return host in allowed
    for item in allowed:
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError:
            if item == host:
                return True
            continue
        if host_ip in network:
            return True
    return False


def enforce_http_auth(request: Request) -> None:
    path = request.url.path
    if path_is_exempt(path):
        return
    state = get_security_state()
    if state.mode == "network-trust":
        host = request.client.host if request.client else None
        if _host_allowed(host, state.allowed_ips):
            return
        raise HTTPException(status_code=403, detail={"error": "ip_not_allowed"})

    # api-key mode
    if not state.api_keys:
        return
    provided = _extract_api_key(request.headers.getlist("x-api-key"), request.headers.get("authorization"))
    if provided in state.api_keys:
        return
    raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})


def websocket_authorized(ws: WebSocket) -> bool:
    state = get_security_state()
    path = ws.url.path
    if path_is_exempt(path):
        return True
    if state.mode == "network-trust":
        host = ws.client.host if ws.client else None
        return _host_allowed(host, state.allowed_ips)
    if not state.api_keys:
        return True
    api_key = ws.query_params.get("api_key", "").strip()
    if not api_key:
        api_key = _extract_api_key(ws.headers.getlist("x-api-key"), ws.headers.get("authorization"))
    return api_key in state.api_keys
