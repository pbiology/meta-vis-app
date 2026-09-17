# tests/unit/test_cli_request_errors.py
#
# ingest.py (repo root) must turn transport failures — unreachable host, TLS,
# proxy, timeout — into a short stderr diagnosis and exit 1, instead of a
# urllib3 stack trace. Upload failures must warn that a blind retry can create
# a duplicate analysis version.

import argparse
import socket
from types import ModuleType

import pytest
import requests

API = "https://meta-vis.example.org"
CASE_URL = f"{API}/api/v1/cases/CASE-1"
UPLOAD_URL = f"{API}/api/v1/ingest/taxprofiler"
RETRY_WARNING = "a retry creates a new analysis version"


def _request_error(
    exc_type: type[requests.exceptions.RequestException], method: str, url: str
) -> requests.exceptions.RequestException:
    request = requests.Request(method, url).prepare()
    return exc_type("simulated failure", request=request)


def _run_main_raising(
    cli: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    exc: requests.exceptions.RequestException,
) -> int:
    """Run cli.main() with the taxprofiler subcommand raising ``exc``."""

    def fail(_args: argparse.Namespace) -> None:
        raise exc

    # Bypass argument parsing so the test does not depend on the CLI's
    # required flags — only the dispatch and error handling are under test.
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda _self: argparse.Namespace(command="taxprofiler"),
    )
    monkeypatch.setattr(cli, "ingest_taxprofiler", fail)
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    code = exit_info.value.code
    assert isinstance(code, int)
    return code


class TestExitOnRequestError:
    def test_unreachable_host_exits_with_a_short_diagnosis(
        self, cli, monkeypatch, capsys
    ):
        exc = _request_error(requests.exceptions.ConnectionError, "GET", CASE_URL)

        code = _run_main_raising(cli, monkeypatch, exc)

        err = capsys.readouterr().err
        assert code == 1
        assert "cannot reach meta-vis.example.org" in err
        assert f"GET {CASE_URL}" in err
        assert "Traceback" not in err

    def test_failure_before_upload_does_not_warn_about_retries(
        self, cli, monkeypatch, capsys
    ):
        exc = _request_error(requests.exceptions.ConnectionError, "GET", CASE_URL)

        _run_main_raising(cli, monkeypatch, exc)

        assert RETRY_WARNING not in capsys.readouterr().err

    def test_upload_failure_warns_that_a_retry_may_duplicate(
        self, cli, monkeypatch, capsys
    ):
        exc = _request_error(requests.exceptions.ConnectionError, "POST", UPLOAD_URL)

        _run_main_raising(cli, monkeypatch, exc)

        assert RETRY_WARNING in capsys.readouterr().err

    def test_tls_error_gets_a_certificate_hint_not_a_network_hint(
        self, cli, monkeypatch, capsys
    ):
        exc = _request_error(requests.exceptions.SSLError, "GET", CASE_URL)

        _run_main_raising(cli, monkeypatch, exc)

        err = capsys.readouterr().err
        assert "TLS/certificate error" in err
        assert "cannot reach" not in err

    def test_read_timeout_says_the_server_did_not_respond(
        self, cli, monkeypatch, capsys
    ):
        exc = _request_error(requests.exceptions.ReadTimeout, "GET", CASE_URL)

        _run_main_raising(cli, monkeypatch, exc)

        assert "did not respond in time" in capsys.readouterr().err


def test_root_cause_unwraps_a_real_connection_failure(cli):
    # Grab a free localhost port and close it, so the connection is refused
    # without touching any external network.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with pytest.raises(requests.exceptions.ConnectionError) as exc_info:
        requests.get(f"http://127.0.0.1:{port}/", timeout=cli.REQUEST_TIMEOUT)

    cause = cli._root_cause(exc_info.value)

    assert isinstance(cause, ConnectionRefusedError)
