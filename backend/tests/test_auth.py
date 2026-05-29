"""Auth-injection tests. Pure — no network, no browser."""

from __future__ import annotations

import base64
import json

import pytest

from sitree.core.auth import (
    AuthConfig,
    cookies_from_storage_state,
    parse_basic_auth,
    parse_cookie_header,
    to_http_auth,
)


def test_parse_cookie_header() -> None:
    assert parse_cookie_header("session=abc; token=xyz") == {"session": "abc", "token": "xyz"}


def test_parse_cookie_header_handles_spaces_and_empty() -> None:
    assert parse_cookie_header("a=1;b=2") == {"a": "1", "b": "2"}
    assert parse_cookie_header("") == {}


def test_parse_basic_auth_splits_user_password() -> None:
    assert parse_basic_auth("alice:s3cret") == ("alice", "s3cret")
    # password may contain colons
    assert parse_basic_auth("bob:a:b:c") == ("bob", "a:b:c")


def test_parse_basic_auth_requires_colon() -> None:
    with pytest.raises(ValueError):
        parse_basic_auth("nopassword")


def test_to_http_auth_basic_sets_authorization_header() -> None:
    auth = to_http_auth(AuthConfig(basic_auth=("alice", "pw")))
    expected = "Basic " + base64.b64encode(b"alice:pw").decode()
    assert auth.headers["Authorization"] == expected
    assert auth.cookies == {}


def test_to_http_auth_cookies() -> None:
    auth = to_http_auth(AuthConfig(cookies="session=abc; token=xyz"))
    assert auth.cookies == {"session": "abc", "token": "xyz"}
    assert auth.headers == {}


def test_to_http_auth_empty() -> None:
    assert to_http_auth(AuthConfig()).is_empty()


def test_storage_state_cookies_filtered_by_host(tmp_path) -> None:
    state = {
        "cookies": [
            {"name": "sid", "value": "1", "domain": "app.example.com"},
            {"name": "wide", "value": "2", "domain": ".example.com"},
            {"name": "other", "value": "3", "domain": "evil.com"},
        ]
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))

    auth = to_http_auth(
        AuthConfig(storage_state_path=path), seed_url="https://app.example.com/dashboard"
    )
    # app.example.com matches exact + parent .example.com; evil.com is excluded.
    assert auth.cookies == {"sid": "1", "wide": "2"}


def test_cookies_from_storage_state_no_host_keeps_all() -> None:
    state = {"cookies": [{"name": "a", "value": "1", "domain": "x.com"}, {"name": "b", "value": "2", "domain": "y.com"}]}
    assert cookies_from_storage_state(state) == {"a": "1", "b": "2"}


def test_cookies_and_storage_state_merge() -> None:
    # Cookie header + basic together.
    auth = to_http_auth(AuthConfig(cookies="a=1", basic_auth=("u", "p")))
    assert auth.cookies == {"a": "1"}
    assert "Authorization" in auth.headers
