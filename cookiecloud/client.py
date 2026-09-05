import base64
import binascii
import hashlib
import json
import os
from urllib.parse import urlencode, urlparse

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from config import REQUEST_TIMEOUT_SECONDS
from runtime_log import log


_COOKIE_CLOUD_CACHE = None
_COOKIE_CLOUD_FETCH_ATTEMPTED = False


def get_cookie_value(env_name: str, domains: list[str]) -> str:
    """Resolve a cookie from direct env config or Cookie Cloud."""
    cookie, _source = resolve_cookie_value(env_name, domains, announce=True)
    return cookie


def resolve_cookie_value(
    env_name: str,
    domains: list[str],
    *,
    announce: bool = False,
) -> tuple[str, str]:
    """Resolve a cookie and return its safe source label."""
    direct_cookie = os.environ.get(env_name, "").strip()
    if direct_cookie:
        return direct_cookie, "environment"

    cookie = _get_cookiecloud_cookie(domains)
    if cookie and announce:
        log(f"{env_name} loaded from Cookie Cloud")
    if cookie:
        return cookie, "Cookie Cloud"
    return "", ""


def _get_cookiecloud_cookie(domains: list[str]) -> str:
    payload = _fetch_cookiecloud_payload()
    if not payload:
        return ""

    cookie_data = payload.get("cookie_data")
    if not isinstance(cookie_data, dict):
        log("Cookie Cloud payload does not contain cookie_data")
        return ""

    matched_hosts = _find_matching_hosts(cookie_data, domains)
    if not matched_hosts:
        log(f"Cookie Cloud did not return cookies for domains: {', '.join(domains)}")
        return ""

    merged = {}
    for host in _sort_hosts_by_specificity(matched_hosts):
        for item in cookie_data.get(host, []):
            name = str(item.get("name", "")).strip()
            value = str(item.get("value", ""))
            if name:
                merged[name] = value

    return "; ".join(f"{name}={value}" for name, value in merged.items())


def _fetch_cookiecloud_payload():
    global _COOKIE_CLOUD_CACHE
    global _COOKIE_CLOUD_FETCH_ATTEMPTED

    if _COOKIE_CLOUD_FETCH_ATTEMPTED:
        return _COOKIE_CLOUD_CACHE

    _COOKIE_CLOUD_FETCH_ATTEMPTED = True

    if _COOKIE_CLOUD_CACHE is not None:
        return _COOKIE_CLOUD_CACHE

    url = os.environ.get("COOKIE_CLOUD_URL", "").strip().rstrip("/")
    uuid = os.environ.get("COOKIE_CLOUD_UUID", "").strip()
    password = os.environ.get("COOKIE_CLOUD_PASSWORD", "").strip()
    crypto_type = os.environ.get("COOKIE_CLOUD_CRYPTO_TYPE", "").strip()

    if not url or not uuid or not password:
        return None

    query = ""
    if crypto_type:
        query = f"?{urlencode({'crypto_type': crypto_type})}"

    endpoint = f"{url}/get/{uuid}{query}"

    payload = _request_cookiecloud_payload("get", endpoint)
    if payload:
        normalized = _normalize_cookiecloud_payload(payload, uuid, password)
        if normalized:
            _COOKIE_CLOUD_CACHE = normalized
            return normalized

    post_payload = _request_cookiecloud_payload(
        "post",
        endpoint,
        json_body={"password": password},
    )

    normalized = _normalize_cookiecloud_payload(post_payload, uuid, password)
    if not normalized:
        return None

    _COOKIE_CLOUD_CACHE = normalized
    return normalized


def _request_cookiecloud_payload(method: str, endpoint: str, json_body: dict | None = None):
    try:
        if method == "get":
            response = requests.get(endpoint, timeout=REQUEST_TIMEOUT_SECONDS)
        else:
            response = requests.post(endpoint, json=json_body, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        log(f"Cookie Cloud {method.upper()} request failed: {exc}")
        return None
    except ValueError as exc:
        log(f"Cookie Cloud returned invalid JSON: {exc}")
        return None

    if not isinstance(payload, dict):
        log("Cookie Cloud payload is not a JSON object")
        return None

    return payload


def _normalize_cookiecloud_payload(payload: dict | None, uuid: str, password: str):
    if not payload:
        return None

    cookie_data = payload.get("cookie_data")
    if isinstance(cookie_data, dict):
        return payload

    encrypted = str(payload.get("encrypted", "")).strip()
    if not encrypted:
        log("Cookie Cloud payload does not contain cookie_data")
        return None

    decrypted = _decrypt_cookiecloud_payload(uuid, password, encrypted)
    if not decrypted:
        return None

    if not isinstance(decrypted.get("cookie_data"), dict):
        log("Cookie Cloud decrypted payload does not contain cookie_data")
        return None

    log("Cookie Cloud payload decrypted client-side")
    return decrypted


def _decrypt_cookiecloud_payload(uuid: str, password: str, encrypted: str):
    try:
        raw_encrypted = base64.b64decode(encrypted)
    except (ValueError, binascii.Error) as exc:
        log(f"Cookie Cloud encrypted payload is not valid base64: {exc}")
        return None

    if len(raw_encrypted) < 16 or raw_encrypted[:8] != b"Salted__":
        log("Cookie Cloud encrypted payload has invalid OpenSSL header")
        return None

    salt = raw_encrypted[8:16]
    ciphertext = raw_encrypted[16:]
    passphrase = hashlib.md5(f"{uuid}-{password}".encode("utf-8")).hexdigest()[:16].encode(
        "utf-8"
    )
    key, iv = _bytes_to_key(salt, passphrase, 32, 16)

    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        unpadded = _pkcs7_unpad(decrypted)
        payload = json.loads(unpadded.decode("utf-8"))
    except Exception as exc:
        log(f"Cookie Cloud client-side decryption failed: {exc}")
        return None

    if not isinstance(payload, dict):
        log("Cookie Cloud decrypted payload is not a JSON object")
        return None

    return payload


def _bytes_to_key(salt: bytes, data: bytes, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    derived = b""
    digest = b""
    while len(derived) < key_len + iv_len:
        digest = hashlib.md5(digest + data + salt).digest()
        derived += digest
    return derived[:key_len], derived[key_len : key_len + iv_len]


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty decrypted payload")

    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("invalid padding length")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid PKCS7 padding")
    return data[:-pad_len]


def _find_matching_hosts(cookie_data: dict, domains: list[str]) -> list[str]:
    normalized_domains = [_normalize_domain(domain) for domain in domains]
    matches = []

    for host in cookie_data.keys():
        normalized_host = _normalize_domain(host)
        if any(_domain_matches(normalized_host, domain) for domain in normalized_domains):
            matches.append(host)

    return matches


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or domain.endswith(f".{host}")


def _sort_hosts_by_specificity(hosts: list[str]) -> list[str]:
    return sorted(hosts, key=lambda host: _host_specificity(_normalize_domain(host)))


def _host_specificity(host: str) -> tuple[int, int, str]:
    labels = [label for label in host.split(".") if label]
    return len(labels), len(host), host


def _normalize_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = parsed.netloc or parsed.path
    return host.split(":", 1)[0].lstrip(".").lower()
