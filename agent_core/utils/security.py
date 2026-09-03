"""Shared production security primitives."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import secrets
import socket
import urllib.parse
import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

import httpx


_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata.google.internal",
    "metadata.google.internal.",
})
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"(?i)\b(?:authorization\s*:\s*bearer|bearer)\s+[A-Za-z0-9._~+/=-]{6,}"),
    re.compile(r"(?i)\b(?:sessionid|auth_token|access_token|api[_-]?key|cookie)\s*[=:]\s*[^\s;,]+"),
)


class UnsafeURLError(ValueError):
    error_code = "SSRF_BLOCKED"

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"{self.error_code}: {reason}")


class SecurityConfigurationError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.error_code = code
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict:
        return {"status": "failed", "error_code": self.error_code}


@dataclass(frozen=True)
class ResolvedPublicURL:
    original_url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]
    pinned_url: str
    host_header: str


def _is_production() -> bool:
    return os.getenv("PINEAL_ENV", "development").strip().lower() in {"production", "prod"}


def security_posture() -> dict:
    """Validate auth posture and describe development's explicit open mode."""
    environment = "production" if _is_production() else "development"
    token = os.getenv("PINEAL_TOKEN", "")
    explicitly_required = os.getenv("PINEAL_REQUIRE_AUTH", "false").strip().lower() == "true"
    required = environment == "production" or explicitly_required
    if required and not token:
        raise SecurityConfigurationError(
            "PRODUCTION_AUTH_REQUIRED" if environment == "production" else "AUTH_TOKEN_REQUIRED",
            "PINEAL_TOKEN must be configured when authentication is required",
        )
    return {
        "environment": environment,
        "auth_required": required or bool(token),
        "auth_state": "ENFORCED" if required or token else "DISABLED_DEVELOPMENT_ONLY",
        "warning_code": None if required or token else "AUTH_DISABLED_DEVELOPMENT_ONLY",
    }


def token_matches(candidate: Optional[str], expected: Optional[str] = None) -> bool:
    expected = os.getenv("PINEAL_TOKEN", "") if expected is None else expected
    if not candidate or not expected:
        return False
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def validate_identifier(value: str, *, field: str = "identifier") -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"INVALID_{field.upper()}")
    return value


def safe_child_path(base: str, filename: str) -> str:
    """Join one filename and prove the result remains below base."""
    if Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError("PATH_TRAVERSAL_BLOCKED")
    root = Path(base).resolve()
    candidate = (root / filename).resolve()
    if root not in candidate.parents:
        raise ValueError("PATH_TRAVERSAL_BLOCKED")
    return str(candidate)


def _resolved_addresses(
    hostname: str,
    port: int,
    resolver: Callable[..., Iterable] = socket.getaddrinfo,
) -> tuple[str, ...]:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            records = resolver(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except (socket.gaierror, OSError) as exc:
            raise UnsafeURLError("DNS_RESOLUTION_FAILED") from exc
        addresses = {record[4][0].split("%", 1)[0] for record in records if record[4]}
    else:
        addresses = {hostname.split("%", 1)[0]}

    if not addresses:
        raise UnsafeURLError("DNS_RESOLUTION_FAILED")
    normalized = []
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeURLError("INVALID_DNS_ADDRESS") from exc
        # is_global blocks private, loopback, link-local, multicast,
        # unspecified, reserved, documentation, and metadata ranges.
        if not ip.is_global:
            raise UnsafeURLError("NON_PUBLIC_ADDRESS")
        normalized.append(ip.compressed)
    return tuple(sorted(normalized))


def resolve_public_url(
    url: str,
    *,
    resolver: Callable[..., Iterable] = socket.getaddrinfo,
) -> ResolvedPublicURL:
    """Validate a URL and pin it to a resolved public address."""
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise UnsafeURLError("INVALID_URL") from exc
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("SCHEME_NOT_ALLOWED")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURLError("URL_CREDENTIALS_NOT_ALLOWED")
    if not parsed.hostname:
        raise UnsafeURLError("HOST_REQUIRED")

    hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise UnsafeURLError("BLOCKED_HOSTNAME")
    port = port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolved_addresses(hostname, port, resolver)
    pinned = addresses[0]
    pinned_host = f"[{pinned}]" if ":" in pinned else pinned
    explicit_port = parsed.port is not None
    netloc = f"{pinned_host}:{port}" if explicit_port else pinned_host
    host_header_name = f"[{hostname}]" if ":" in hostname else hostname
    host_header = f"{host_header_name}:{port}" if explicit_port else host_header_name
    pinned_url = urllib.parse.urlunsplit((
        parsed.scheme,
        netloc,
        parsed.path or "/",
        parsed.query,
        "",
    ))
    return ResolvedPublicURL(
        original_url=url,
        hostname=hostname,
        port=port,
        addresses=addresses,
        pinned_url=pinned_url,
        host_header=host_header,
    )


def is_safe_url(url: str) -> bool:
    """Compatibility predicate; DNS failures and non-public answers fail closed."""
    try:
        resolve_public_url(url)
    except (UnsafeURLError, UnicodeError):
        return False
    return True


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    max_redirects: int = 3,
    stream: bool = False,
) -> httpx.Response:
    """GET with DNS pinning and validation of every redirect target."""
    current_url = url
    for redirect_count in range(max_redirects + 1):
        resolved = await asyncio.to_thread(resolve_public_url, current_url)
        request_headers = dict(headers or {})
        request_headers["Host"] = resolved.host_header
        request = client.build_request("GET", resolved.pinned_url, headers=request_headers)
        if request.url.scheme == "https":
            request.extensions["sni_hostname"] = resolved.hostname
        response = await client.send(request, stream=stream)
        if response.status_code not in _REDIRECT_CODES:
            response.extensions["pineal_original_url"] = current_url
            response.extensions["pineal_resolved_addresses"] = resolved.addresses
            return response

        location = response.headers.get("location")
        await response.aclose()
        if not location:
            raise UnsafeURLError("REDIRECT_WITHOUT_LOCATION")
        if redirect_count >= max_redirects:
            raise UnsafeURLError("TOO_MANY_REDIRECTS")
        current_url = urllib.parse.urljoin(current_url, location)
    raise UnsafeURLError("TOO_MANY_REDIRECTS")


@functools.lru_cache(maxsize=1)
def _environment_secret_values() -> tuple[str, ...]:
    markers = ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE")
    return tuple(
        value
        for name, value in os.environ.items()
        if value and len(value) >= 6 and any(marker in name.upper() for marker in markers)
    )


def redact_text(value: object, *, extra_secrets: Iterable[str] = ()) -> str:
    text = str(value)
    for secret in (*_environment_secret_values(), *tuple(extra_secrets)):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def redact_structure(value: object) -> object:
    if isinstance(value, dict):
        return {key: redact_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_structure(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value
