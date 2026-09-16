"""CORS allow-list hardening.

The deployed API was trusting http://localhost alongside its real origin.
Because CORS runs with credentials enabled, that let a page on a victim's
machine make authenticated calls using their refresh cookie. The environment
had to be edited to fix it, which is exactly the kind of thing that gets
forgotten -- so the rule is enforced in code and covered here.
"""
import pytest

from app.config import Settings, _is_local_http_origin

DEPLOYED = "https://lemarboks.github.io"


def origins(value: str, allow_local: bool = False) -> list[str]:
    return Settings(cors_origins=value, cors_allow_local_origins=allow_local).allowed_origins


def test_a_purely_local_stack_is_untouched():
    """Local development lists only http://localhost and must keep working."""
    assert origins("http://localhost:3000,http://localhost:8081") == [
        "http://localhost:3000",
        "http://localhost:8081",
    ]


def test_local_origins_are_dropped_once_a_deployed_origin_is_present():
    assert origins(f"{DEPLOYED},http://localhost:3000,http://localhost:8081") == [DEPLOYED]


def test_loopback_spellings_are_all_recognised():
    value = f"{DEPLOYED},http://127.0.0.1:3000,http://[::1]:3000,http://0.0.0.0:8081,http://app.localhost:3000"
    assert origins(value) == [DEPLOYED]


def test_https_localhost_is_kept_since_it_is_not_the_credential_risk():
    """The concern is a plain-http page on the user's machine; an https
    localhost origin is a deliberate, separate choice."""
    assert origins(f"{DEPLOYED},https://localhost:3000") == [DEPLOYED, "https://localhost:3000"]


def test_the_escape_hatch_restores_the_previous_behaviour():
    value = f"{DEPLOYED},http://localhost:3000"
    assert origins(value, allow_local=True) == [DEPLOYED, "http://localhost:3000"]


def test_unrelated_http_origins_are_not_stripped():
    """Only local origins are filtered; a non-local http origin is someone's
    deliberate configuration and is left alone."""
    assert origins(f"{DEPLOYED},http://internal.example:8080") == [
        DEPLOYED,
        "http://internal.example:8080",
    ]


@pytest.mark.parametrize(
    "origin,expected",
    [
        ("http://localhost", True),
        ("http://localhost:3000", True),
        ("http://127.0.0.1:8000", True),
        ("http://[::1]:3000", True),
        ("http://admin.localhost:3000", True),
        ("HTTP://LOCALHOST:3000", True),
        ("https://localhost:3000", False),
        ("http://example.com", False),
        ("http://notlocalhost.com", False),
        ("https://lemarboks.github.io", False),
    ],
)
def test_local_http_origin_detection(origin, expected):
    assert _is_local_http_origin(origin) is expected


def test_whitespace_and_empty_entries_are_ignored():
    assert origins(f" {DEPLOYED} , , http://localhost:3000 ") == [DEPLOYED]
