"""End to end: whole patch files through the command line, compared with a result kept in a file.

Every folder under tests/e2e/cases is one case. It holds old.csv and new.csv, and the result:

- cases/success/<case>/expected.txt: the report that the tool must print, with exit code 0
- cases/error/<case>/expected_error.txt: the error the tool must print, with exit code 2 and no report

To add a case, add a folder. No Python is needed.
"""

from pathlib import Path

import pytest

from patchdiff.__main__ import main

SUCCESS_CASES = Path(__file__).parent / "cases" / "success"
ERROR_CASES = Path(__file__).parent / "cases" / "error"


def case_names(folder: Path) -> list[str]:
    return sorted(case.name for case in folder.iterdir() if case.is_dir())


@pytest.mark.parametrize("case", case_names(SUCCESS_CASES))
def test_command_line_prints_expected_report_and_returns_zero_when_patches_are_valid(case, capsys, monkeypatch):
    # Run inside the case folder, so that the report shows short file names
    monkeypatch.chdir(SUCCESS_CASES / case)
    exit_code = main(["old.csv", "new.csv"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == Path("expected.txt").read_text(encoding="utf-8")
    assert exit_code == 0


@pytest.mark.parametrize("case", case_names(ERROR_CASES))
def test_command_line_prints_expected_error_and_returns_two_when_input_is_bad(case, capsys, monkeypatch):
    # Run inside the case folder, so that the error shows short file names
    monkeypatch.chdir(ERROR_CASES / case)
    exit_code = main(["old.csv", "new.csv"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == Path("expected_error.txt").read_text(encoding="utf-8")
    assert exit_code == 2
