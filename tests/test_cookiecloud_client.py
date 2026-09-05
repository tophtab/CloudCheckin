import pytest

from cookiecloud import client
from tests.log_assertions import assert_timestamped_lines


@pytest.fixture(autouse=True)
def _reset_cookiecloud_fetch_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, "_COOKIE_CLOUD_CACHE", None)
    monkeypatch.setattr(client, "_COOKIE_CLOUD_FETCH_ATTEMPTED", False)


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


def test_parse_cookiecloud_single_var_accepts_shared_multiline_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_value = (
        "\n"
        "host=http://192.168.31.100:8088\n"
        "# comment line is ignored\n"
        "uuid=abc123\n"
        "password=secret\n"
        "domain=chatglm.cn\n"
        "unknown_key=ignored\n"
    )

    assert client._parse_cookiecloud_single_var(raw_value) == {
        "host": "http://192.168.31.100:8088",
        "uuid": "abc123",
        "password": "secret",
    }
    assert capsys.readouterr().out == ""


def test_parse_cookiecloud_single_var_normalizes_keys_and_host() -> None:
    raw_value = "HOST=http://example.com/\nUuid=u1\nPASSWORD=p1\n"

    assert client._parse_cookiecloud_single_var(raw_value) == {
        "host": "http://example.com",
        "uuid": "u1",
        "password": "p1",
    }


def test_parse_cookiecloud_single_var_returns_none_and_logs_missing_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_value = "host=http://example.com\nuuid=u1\n"

    assert client._parse_cookiecloud_single_var(raw_value) is None

    output_lines = assert_timestamped_lines(capsys.readouterr().out)
    assert any("password" in line for line in output_lines)


def test_fetch_cookiecloud_payload_prefers_single_variable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "COOKIECLOUD",
        "host=http://single.example\nuuid=single-uuid\npassword=single-pass",
    )
    monkeypatch.setenv("COOKIE_CLOUD_URL", "http://legacy.example")
    monkeypatch.setenv("COOKIE_CLOUD_UUID", "legacy-uuid")
    monkeypatch.setenv("COOKIE_CLOUD_PASSWORD", "legacy-pass")

    endpoints = []

    def fake_request(method: str, endpoint: str, json_body: dict | None = None):
        endpoints.append((method, endpoint))
        return {"cookie_data": {}}

    monkeypatch.setattr(client, "_request_cookiecloud_payload", fake_request)

    assert client._fetch_cookiecloud_payload() == {"cookie_data": {}}
    assert endpoints[0] == ("get", "http://single.example/get/single-uuid")

    output_lines = assert_timestamped_lines(capsys.readouterr().out)
    assert any("Using single-variable COOKIECLOUD config" in line for line in output_lines)


def test_fetch_cookiecloud_payload_single_variable_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COOKIECLOUD", "host=http://single.example\nuuid=single-uuid\n")
    monkeypatch.setenv("COOKIE_CLOUD_URL", "http://legacy.example/")
    monkeypatch.setenv("COOKIE_CLOUD_UUID", "legacy-uuid")
    monkeypatch.setenv("COOKIE_CLOUD_PASSWORD", "legacy-pass")

    endpoints = []

    def fake_request(method: str, endpoint: str, json_body: dict | None = None):
        endpoints.append((method, endpoint))
        return {"cookie_data": {}}

    monkeypatch.setattr(client, "_request_cookiecloud_payload", fake_request)

    assert client._fetch_cookiecloud_payload() == {"cookie_data": {}}
    assert endpoints[0] == ("get", "http://legacy.example/get/legacy-uuid")


def test_fetch_cookiecloud_payload_legacy_variables_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIECLOUD", raising=False)
    monkeypatch.setenv("COOKIE_CLOUD_URL", "http://legacy.example")
    monkeypatch.setenv("COOKIE_CLOUD_UUID", "legacy-uuid")
    monkeypatch.setenv("COOKIE_CLOUD_PASSWORD", "legacy-pass")

    endpoints = []

    def fake_request(method: str, endpoint: str, json_body: dict | None = None):
        endpoints.append((method, endpoint))
        return {"cookie_data": {}}

    monkeypatch.setattr(client, "_request_cookiecloud_payload", fake_request)

    assert client._fetch_cookiecloud_payload() == {"cookie_data": {}}
    assert endpoints[0] == ("get", "http://legacy.example/get/legacy-uuid")


def test_fetch_cookiecloud_payload_returns_none_without_any_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIECLOUD", raising=False)
    monkeypatch.delenv("COOKIE_CLOUD_URL", raising=False)
    monkeypatch.delenv("COOKIE_CLOUD_UUID", raising=False)
    monkeypatch.delenv("COOKIE_CLOUD_PASSWORD", raising=False)

    def fail_request(method: str, endpoint: str, json_body: dict | None = None):
        raise AssertionError("Cookie Cloud should not be requested without config")

    monkeypatch.setattr(client, "_request_cookiecloud_payload", fail_request)

    assert client._fetch_cookiecloud_payload() is None
