"""Centralized configuration for codercheckin."""

import os

# Network timeouts
REQUEST_TIMEOUT_SECONDS = 30

# curl_cffi floor: verified against 0.14.x through 0.16.x (session impersonate,
# module-level get, cookie jar all unchanged). The import-time check only blocks
# versions older than the floor so Qinglong can share the latest build with
# other scripts.
MIN_CURL_CFFI_VERSION = "0.14"

# User agents
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9"
DEFAULT_SEC_CH_UA = '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"'
DEFAULT_SEC_CH_UA_PLATFORM = '"Windows"'
DEFAULT_BROWSER_IMPERSONATE = "chrome131"

# Delay range for multi-account check-in (seconds)
DEFAULT_DELAY_RANGE_SECONDS = (1, 20)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with default value."""
    return os.environ.get(key, default).strip()


def get_env_required(key: str) -> str:
    """Get required environment variable, raise if not set."""
    value = get_env(key)
    if not value:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value
