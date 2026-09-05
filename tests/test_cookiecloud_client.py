import pytest

from cookiecloud import client
from tests.log_assertions import assert_timestamped_lines


def _cookie_header_to_dict(cookie_header: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in cookie_header.split("; ") if part)


def test_resolve_cookie_value_prefers_direct_environment_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V2EX_COOKIE", "sid=direct")

    def fail_cookiecloud_lookup(domains: list[str]) -> str:
        raise AssertionError("Cookie Cloud should not be used when direct cookie exists")

    monkeypatch.setattr(client, "_get_cookiecloud_cookie", fail_cookiecloud_lookup)

    assert client.resolve_cookie_value("V2EX_COOKIE", ["v2ex.com"]) == (
        "sid=direct",
        "environment",
    )


def test_resolve_cookie_value_reports_cookiecloud_source(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("V2EX_COOKIE", raising=False)
    monkeypatch.setattr(client, "_get_cookiecloud_cookie", lambda domains: "sid=cloud")

    assert client.resolve_cookie_value("V2EX_COOKIE", ["v2ex.com"], announce=True) == (
        "sid=cloud",
        "Cookie Cloud",
    )
    output_lines = assert_timestamped_lines(capsys.readouterr().out)
    assert len(output_lines) == 1
    assert "V2EX_COOKIE loaded from Cookie Cloud" in output_lines[0]


def test_cookiecloud_cookie_header_prefers_most_specific_duplicate_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "_fetch_cookiecloud_payload",
        lambda: {
            "cookie_data": {
                "v2ex.com": [
                    {"name": "A2", "value": "base-a2"},
                    {"name": "base_only", "value": "kept"},
                ],
                "www.v2ex.com": [
                    {"name": "A2", "value": "www-a2"},
                    {"name": "PB3_SESSION", "value": "www-session"},
                ],
            }
        },
    )

    cookie_header = client._get_cookiecloud_cookie(["v2ex.com", "www.v2ex.com"])

    cookies = _cookie_header_to_dict(cookie_header)
    assert cookies == {
        "A2": "www-a2",
        "base_only": "kept",
        "PB3_SESSION": "www-session",
    }


def test_cookiecloud_cookie_header_ignores_unrequested_subdomains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "_fetch_cookiecloud_payload",
        lambda: {
            "cookie_data": {
                "api.v2ex.com": [
                    {"name": "A2", "value": "api-a2"},
                    {"name": "api_only", "value": "ignored"},
                ],
                "www.v2ex.com": [
                    {"name": "PB3_SESSION", "value": "www-session"},
                ],
            }
        },
    )

    cookie_header = client._get_cookiecloud_cookie(["v2ex.com", "www.v2ex.com"])

    cookies = _cookie_header_to_dict(cookie_header)
    assert cookies == {"PB3_SESSION": "www-session"}
