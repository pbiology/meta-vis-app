# tests/unit/test_cli_request_errors.py
#
# ingest.py (repo root) must turn transport failures — unreachable host, TLS,
# proxy, timeout — into a short stderr diagnosis and exit 1, instead of a
# urllib3 stack trace. Upload failures must warn that a blind retry can create
# a duplicate analysis version.

import argparse
import socket
import threading
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
        lambda _self: argparse.Namespace(
            command="taxprofiler", url=API, keycloak_url=API
        ),
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


# ---------------------------------------------------------------------------
# A connection that opened and then broke must not be reported as an
# unreachable host. Real local sockets, so the exception chain is the one
# urllib3 actually produces rather than a hand-built imitation.
# ---------------------------------------------------------------------------


def _local_server(on_connect) -> tuple[socket.socket, int]:
    """Listen on a free localhost port and run ``on_connect(conn)`` once."""
    server = socket.socket()
    # A tiny receive buffer makes an unread upload fill the socket at once.
    server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            on_connect(conn)

    threading.Thread(target=serve, daemon=True).start()
    return server, server.getsockname()[1]


def _failed_upload(port: int) -> requests.exceptions.RequestException:
    url = f"http://127.0.0.1:{port}/api/v1/ingest/taxprofiler"
    with pytest.raises(requests.exceptions.RequestException) as exc_info:
        requests.post(
            url,
            files={"bundle": ("bundle.tar.gz", b"x" * (8 * 1024 * 1024))},
            timeout=(0.5, None),
        )
    return exc_info.value


class TestConnectionBrokenMidRequest:
    def test_stalled_upload_says_the_server_stopped_reading(
        self, cli, monkeypatch, capsys
    ):
        stop = threading.Event()
        server, port = _local_server(lambda _conn: stop.wait(5))
        try:
            exc = _failed_upload(port)
        finally:
            stop.set()
            server.close()

        _run_main_raising(cli, monkeypatch, exc)

        err = capsys.readouterr().err
        assert "broke during the request" in err
        assert "stopped reading the request" in err
        assert "cannot reach" not in err
        assert RETRY_WARNING in err

    def test_server_closing_mid_upload_says_it_closed_the_connection(
        self, cli, monkeypatch, capsys
    ):
        server, port = _local_server(lambda conn: conn.recv(1024))
        try:
            exc = _failed_upload(port)
        finally:
            server.close()

        _run_main_raising(cli, monkeypatch, exc)

        err = capsys.readouterr().err
        assert "broke during the request" in err
        assert "closed the connection" in err
        assert "cannot reach" not in err
        assert RETRY_WARNING in err


def test_refused_connection_is_not_mistaken_for_a_broken_one(cli):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with pytest.raises(requests.exceptions.ConnectionError) as exc_info:
        requests.get(f"http://127.0.0.1:{port}/", timeout=cli.REQUEST_TIMEOUT)

    assert not cli._connection_was_established(exc_info.value)


def test_upload_tolerates_send_stalls_longer_than_the_connect_timeout(cli):
    # The first value is also the send timeout in urllib3; tying it back to
    # CONNECT_TIMEOUT_S reintroduces aborted uploads on a brief server pause.
    send_timeout, read_timeout = cli.UPLOAD_TIMEOUT
    assert send_timeout >= 60
    assert read_timeout is None
