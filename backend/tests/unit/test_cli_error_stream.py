# tests/unit/test_cli_error_stream.py
#
# ingest.py (repo root) must write every error and warning to stderr, never
# stdout. A wrapper that redirects stdout to a log would otherwise hide why an
# ingest failed. Each test asserts stdout stays empty, which is what catches a
# message regressing back onto the wrong stream.

from pathlib import Path
from types import ModuleType

import pytest

TAXPROFILER_SAMPLE = "sample_id=S1 type=sample subject_id=P1 nucleic_acid=DNA"


class _FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def get(self, _url: str, **_kwargs: object) -> _FakeResponse:
        return self._response


def _assert_fails_on_stderr(
    capsys: pytest.CaptureFixture[str], exit_info: pytest.ExceptionInfo[SystemExit]
) -> str:
    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert captured.out == ""
    assert captured.err != ""
    return captured.err


class TestParseErrorsGoToStderr:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("", "Empty --classifier argument"),
            ("kraken2 db", "Invalid classifier token 'db'"),
            ("kraken2 db=k2", "missing required keys"),
        ],
    )
    def test_classifier(
        self,
        cli: ModuleType,
        capsys: pytest.CaptureFixture[str],
        raw: str,
        expected: str,
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli.parse_classifier(raw)

        assert expected in _assert_fails_on_stderr(capsys, exit_info)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("sample_id", "Invalid sample token 'sample_id'"),
            ("sample_id=S1 type=sample", "missing required keys"),
            (
                "sample_id=S1 type=sample nucleic_acid=DNA column_kraken2=S1",
                "must provide subject_id",
            ),
            (f"{TAXPROFILER_SAMPLE} column_bracken=S1", "not declared"),
            (TAXPROFILER_SAMPLE, "has no classifier columns"),
            (f"{TAXPROFILER_SAMPLE} column_kraken2=S1 sex=x", "invalid sex='x'"),
            (
                f"{TAXPROFILER_SAMPLE} material=DNA column_kraken2=S1",
                "sets both nucleic_acid and the deprecated material",
            ),
        ],
    )
    def test_taxprofiler_sample(
        self,
        cli: ModuleType,
        capsys: pytest.CaptureFixture[str],
        raw: str,
        expected: str,
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli.parse_sample(raw, ["kraken2"])

        assert expected in _assert_fails_on_stderr(capsys, exit_info)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("sample_id", "Invalid sample token 'sample_id'"),
            ("sample_id=S1 type=sample nucleic_acid=DNA", "missing required keys"),
            (
                "sample_id=S1 type=sample nucleic_acid=DNA abundance_path=a.tsv",
                "must provide subject_id",
            ),
        ],
    )
    def test_trana_sample(
        self,
        cli: ModuleType,
        capsys: pytest.CaptureFixture[str],
        raw: str,
        expected: str,
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli.parse_trana_sample(raw)

        assert expected in _assert_fails_on_stderr(capsys, exit_info)

    def test_duplicate_sample_ids(
        self, cli: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli._check_unique_sample_ids([{"sample_id": "S1"}, {"sample_id": "S1"}])

        assert "Duplicate sample_id" in _assert_fails_on_stderr(capsys, exit_info)


class TestPathChecksGoToStderr:
    def test_missing_file(
        self, cli: ModuleType, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli._check_file(str(tmp_path / "absent.json"), "--multiqc")

        assert "--multiqc is not a file" in _assert_fails_on_stderr(capsys, exit_info)

    def test_missing_directory(
        self, cli: ModuleType, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            cli._check_dir(str(tmp_path / "absent"), "--metaval")

        err = _assert_fails_on_stderr(capsys, exit_info)
        assert "--metaval is not a directory" in err


class TestServerResponsesGoToStderr:
    def test_failed_ingest(
        self, cli: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        response = _FakeResponse(422, "bad bundle")

        with pytest.raises(SystemExit) as exit_info:
            cli._print_result(response, "CASE-1")

        err = _assert_fails_on_stderr(capsys, exit_info)
        assert "Ingest failed (422): bad bundle" in err

    def test_unexpected_preflight_status_warns_and_continues(
        self, cli: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        session = _FakeSession(_FakeResponse(500, "boom"))

        cli.check_case_available(session, "https://meta-vis.example.org", "CASE-1")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "preflight case check returned 500" in captured.err
