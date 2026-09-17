# tests/unit/test_cli_url_validation.py
#
# ingest.py (repo root) sends credentials to --keycloak-url and a bearer token
# to --url, so both must be HTTPS unless the host is loopback. Invalid URLs
# must be rejected before any request is made, with a message that says why.

from typing import NoReturn

import pytest
import requests


class UrlRejected(Exception):
    """Raised by the stand-in for argparse's parser.error."""


def _error(message: str) -> NoReturn:
    raise UrlRejected(message)


class TestValidateBaseUrl:
    @pytest.mark.parametrize(
        "raw",
        [
            "https://meta-vis.example.org",
            "https://meta-vis.example.org:8443",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://[::1]:8000",
        ],
    )
    def test_https_and_loopback_http_are_accepted(self, cli, raw):
        assert cli._validate_base_url(raw, "--url", _error) == raw

    def test_trailing_slash_is_stripped(self, cli):
        result = cli._validate_base_url(
            "https://meta-vis.example.org/", "--url", _error
        )

        assert result == "https://meta-vis.example.org"

    @pytest.mark.parametrize(
        "raw",
        [
            "http://meta-vis.example.org",
            # Starts with "localhost" but resolves elsewhere.
            "http://localhost.example.org",
            # Private, but not loopback: traffic still crosses a network.
            "http://10.0.0.5:8000",
        ],
    )
    def test_http_to_a_non_local_host_is_refused_with_the_reason(self, cli, raw):
        with pytest.raises(UrlRejected) as exc_info:
            cli._validate_base_url(raw, "--keycloak-url", _error)

        message = str(exc_info.value)
        assert "--keycloak-url" in message
        assert "unencrypted" in message
        assert raw.replace("http://", "https://") in message

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ftp://meta-vis.example.org", "not a valid base URL"),
            ("https://", "not a valid base URL"),
            ("meta-vis.example.org", "not a valid base URL"),
            ("https://meta-vis.example.org:notaport", "not a valid URL"),
            (
                "https://user:secret@meta-vis.example.org",
                "must not contain credentials",
            ),
            ("https://meta-vis.example.org?x=1", "without '?' or '#'"),
            ("https://meta-vis.example.org#x", "without '?' or '#'"),
        ],
    )
    def test_malformed_urls_are_refused(self, cli, raw, expected):
        with pytest.raises(UrlRejected) as exc_info:
            cli._validate_base_url(raw, "--url", _error)

        assert expected in str(exc_info.value)


@pytest.mark.parametrize(
    "raw",
    [
        "https://user:s3cr3t-value@meta-vis.example.org",
        # Also invalid in other ways — the credentials check must win.
        "ftp://user:s3cr3t-value@meta-vis.example.org?x=1",
    ],
)
def test_credentials_are_not_echoed_in_the_rejection(cli, raw):
    with pytest.raises(UrlRejected) as exc_info:
        cli._validate_base_url(raw, "--url", _error)

    assert "s3cr3t-value" not in str(exc_info.value)


def test_case_id_is_encoded_so_it_cannot_change_the_api_path(cli):
    requested: list[str] = []

    class RecordingSession:
        def get(self, url: str, **_kwargs: object) -> requests.Response:
            requested.append(url)
            response = requests.Response()
            response.status_code = 404
            return response

    cli.check_case_available(
        RecordingSession(),
        "https://meta-vis.example.org",
        "X/analyses/2?#",
        assume_yes=True,
    )

    assert requested == [
        "https://meta-vis.example.org/api/v1/cases/X%2Fanalyses%2F2%3F%23"
    ]
