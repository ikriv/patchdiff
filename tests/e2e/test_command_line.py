"""End to end: things about the command line that are not tied to one case folder."""

import locale
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from patchdiff.__main__ import main

REPO_ROOT = Path(__file__).parents[2]
SUCCESS_CASES = Path(__file__).parent / "cases" / "success"
CASE_NAMES = sorted(case.name for case in SUCCESS_CASES.iterdir() if case.is_dir())
SAMPLE = SUCCESS_CASES / "sample_patch3_to_patch4"


@pytest.mark.parametrize("case", CASE_NAMES)
@pytest.mark.parametrize("file_name", ["old.csv", "new.csv"])
def test_command_line_reports_no_differences_when_patch_is_compared_with_its_copy(case, file_name, tmp_path, capsys):
    original = SUCCESS_CASES / case / file_name
    copy = tmp_path / "copy.csv"
    shutil.copyfile(original, copy)
    # The warnings of a patch and of its copy are the same, they are not a difference
    exit_code = main(["--no-warnings", str(original), str(copy)])
    report = capsys.readouterr().out
    assert exit_code == 0
    assert report == (
        f"Old: {file_name}\n"
        "New: copy.csv\n"
        "\n"
        "No differences: the two patches do the same thing.\n"
    )


def run_in_new_process_with_hash_seed(hash_seed: str, arguments: list[str]) -> str:
    """Run the tool in a new Python process and return what it prints.

    The order of a set of strings depends on a hash seed, which Python picks anew for
    every process. Inside one process the order never changes, so a test that runs the
    tool twice in one process cannot catch output that depends on that order.
    """
    result = subprocess.run(
        [sys.executable, "-m", "patchdiff", *arguments],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def test_command_line_prints_utf8_when_the_console_encoding_cannot_show_the_values(tmp_path):
    """Without sys.stdout.reconfigure the tool would crash on a Windows code page with a value like 'ř'."""
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_text("BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Dvořák\n", encoding="utf-8")
    new.write_text("BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Němcová\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "patchdiff", str(old), str(new)],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    report = result.stdout.decode("utf-8").replace("\r\n", "\n")  # Windows writes CRLF to a pipe
    assert "Modified Issuer 'CEZ': Changed Analyst from 'Dvořák' to 'Němcová'\n" in report


def test_command_line_prints_error_and_returns_two_when_a_path_is_a_folder(tmp_path, capsys):
    (tmp_path / "old.csv").write_text("BeginDate,EndDate,Issuer,Country\n", encoding="utf-8")
    exit_code = main([str(tmp_path / "old.csv"), str(tmp_path)])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert exit_code == 2


# Two cases with several keys and columns are enough. Every case would cost 28 processes.
@pytest.mark.parametrize("case", ["every_kind_of_warning", "task_document_example"])
def test_command_line_prints_identical_report_when_run_in_processes_with_different_hash_seeds(case):
    arguments = [str(SUCCESS_CASES / case / "old.csv"), str(SUCCESS_CASES / case / "new.csv")]
    reports = {run_in_new_process_with_hash_seed(hash_seed, arguments) for hash_seed in ("1", "2", "3", "4")}
    assert len(reports) == 1


WARNINGS_CASE = SUCCESS_CASES / "every_kind_of_warning"


def test_command_line_prints_warnings_after_the_differences_when_no_option_is_given(capsys):
    exit_code = main([str(WARNINGS_CASE / "old.csv"), str(WARNINGS_CASE / "new.csv")])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "\nWARNINGS\n\nNew Patch:\n    Row 5: Issuer is blank, the row does nothing\n" in captured.out
    assert exit_code == 0


def test_command_line_prints_only_the_differences_when_no_warnings_option_is_given(capsys):
    main([str(WARNINGS_CASE / "old.csv"), str(WARNINGS_CASE / "new.csv")])
    with_warnings = capsys.readouterr().out
    exit_code = main(["--no-warnings", str(WARNINGS_CASE / "old.csv"), str(WARNINGS_CASE / "new.csv")])
    without_warnings = capsys.readouterr().out
    assert exit_code == 0
    assert "WARNINGS" not in without_warnings
    assert with_warnings.startswith(without_warnings + "\nWARNINGS\n")


def test_command_line_prints_no_warnings_part_when_neither_patch_has_warnings(capsys):
    case = SUCCESS_CASES / "task_document_example"
    exit_code = main([str(case / "old.csv"), str(case / "new.csv")])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        "Old: old.csv\n"
        "New: new.csv\n"
        "\n"
        "Now patching Issuer 'IRM':\n"
        "    Added Analyst 'Emily'\n"
        "    Added Sector 'Real Estate'\n"
        "Modified Issuer 'MSFT': Changed Analyst from 'Bob' to 'Mike'\n"
        "Modified Issuer 'TSLA': Added Analyst 'Bob'\n"
    )
    assert exit_code == 0


def test_command_line_stops_with_usage_error_when_only_one_file_is_given(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([str(SAMPLE / "old.csv")])
    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert "the following arguments are required: new" in captured.err


def test_command_line_prints_error_naming_the_file_and_returns_two_when_a_file_is_not_found(tmp_path, capsys):
    exit_code = main([str(SAMPLE / "old.csv"), str(tmp_path / "missing.csv")])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "missing.csv" in captured.err
    assert exit_code == 2


def test_report_shows_full_paths_when_both_files_have_the_same_name(tmp_path, capsys):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    for folder in ("a", "b"):
        (tmp_path / folder / "patch.csv").write_text("BeginDate,EndDate,Issuer,Country\n", encoding="utf-8")
    old, new = tmp_path / "a" / "patch.csv", tmp_path / "b" / "patch.csv"
    main([str(old), str(new)])
    report = capsys.readouterr().out
    assert f"Old: {old}\n" in report
    assert f"New: {new}\n" in report


def test_command_line_reads_both_files_in_given_encoding_when_encoding_option_is_passed(tmp_path, capsys):
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_bytes("BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Dvořák\n".encode("cp1250"))
    new.write_bytes("BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Němcová\n".encode("cp1250"))
    exit_code = main([str(old), str(new), "--encoding", "cp1250"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Issuer 'CEZ': Changed Analyst from 'Dvořák' to 'Němcová'\n" in captured.out
    assert exit_code == 0


def test_command_line_prints_error_naming_the_file_and_returns_two_when_file_cannot_be_read_in_any_encoding(
    tmp_path, capsys, monkeypatch
):
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_bytes(b"BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Bob\n")
    new.write_bytes("BeginDate,EndDate,Issuer,Analyst\n,,CEZ,Dvořák\n".encode("cp1250"))
    # The test must not depend on the encoding of the machine it runs on
    monkeypatch.setattr(locale, "getencoding", lambda: "ascii")
    exit_code = main([str(old), str(new)])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"error: {new}: cannot read the file as UTF-8 or as ascii (the local encoding), "
        "use --encoding to name the encoding of the file\n"
    )
    assert exit_code == 2
