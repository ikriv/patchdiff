import locale
from datetime import date

import pytest

from patchdiff.model.patch_model import DateRange, NoOpRowReason, PatchError, PatchText
from patchdiff.parser import load_patch, parse_date, parse_patch, read_patch_text


def test_parse_date_reads_same_date_when_written_as_yyyymmdd_yyyy_mm_dd_or_mm_dd_yyyy():
    assert parse_date("20240201") == date(2024, 2, 1)
    assert parse_date("2024-02-01") == date(2024, 2, 1)
    assert parse_date("02/01/2024") == date(2024, 2, 1)
    assert parse_date("2/1/2024") == date(2024, 2, 1)
    assert parse_date("") is None


def test_parse_date_reads_month_first_when_date_has_slashes():
    assert parse_date("1/4/2025") == date(2025, 1, 4)
    with pytest.raises(ValueError):
        parse_date("13/1/2025")


@pytest.mark.parametrize(
    "text", ["01.02.2024", "Feb 1", "2024021", "202402011", "2024-2-1", "2024-02-30", "02/30/2024", "20241301"]
)
def test_parse_date_raises_error_when_text_is_not_a_date(text):
    with pytest.raises(ValueError):
        parse_date(text)


def test_parser_takes_first_column_as_key_when_dates_come_after_it(make_patch):
    patch = make_patch("""
        Issuer,BeginDate,EndDate,Analyst,Sector
        MSFT,,,Bob,Information Technology
    """)
    assert patch.key_column == "Issuer"
    assert list(patch.value_columns) == ["Analyst", "Sector"]


def test_parser_takes_first_non_date_column_as_key_when_dates_come_first(make_patch):
    patch = make_patch("""
        BeginDate,Issuer,EndDate,Analyst
        1/1/2024,CAT,1/31/2024,Emily
    """)
    assert patch.key_column == "Issuer"
    row = patch.rows[0]
    assert row.key == "CAT"
    assert row.dates == DateRange.from_dates(date(2024, 1, 1), date(2024, 1, 31))
    assert row.values == {"Analyst": "Emily"}


def test_parser_trims_whitespace_and_keeps_case_when_reading_cells(make_patch):
    patch = make_patch("""
        BeginDate , EndDate,  Issuer , Analyst
         20240101 ,,  msft ,   Bob
    """)
    assert patch.key_column == "Issuer"
    assert list(patch.value_columns) == ["Analyst"]
    row = patch.rows[0]
    assert row.key == "msft"
    assert row.dates.first_day == date(2024, 1, 1)
    assert row.dates.last_day is None
    assert row.values == {"Analyst": "Bob"}


def test_parser_leaves_value_out_when_cell_is_blank(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,TSLA,  ,Consumer Discretionary
    """)
    assert patch.rows[0].values == {"Sector": "Consumer Discretionary"}


def test_parser_keeps_file_line_numbers_when_blank_lines_are_skipped(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,MSFT,Bob

        ,,,
        ,,CAT,Emily
    """)
    assert [(row.line, row.key) for row in patch.rows] == [(2, "MSFT"), (5, "CAT")]


def test_parser_reads_missing_cells_as_blank_when_row_is_short(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,MSFT
    """)
    assert patch.rows[0].values == {}


def test_parser_ignores_unnamed_columns_when_they_are_empty(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,,
        ,,MSFT,Bob,,
    """)
    assert list(patch.value_columns) == ["Analyst"]


def test_parser_accepts_row_as_noop_when_begin_date_is_after_end_date(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        20240301,20240201,MSFT,Bob
    """)
    assert patch.rows[0].dates.is_reversed
    assert patch.rows[0].is_noop


def test_parser_marks_row_as_noop_when_key_is_blank(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,,Bob
    """)
    assert patch.rows[0].is_noop


def test_row_is_noop_with_a_reason_when_it_has_blank_key_reversed_dates_or_no_values(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,MSFT,Bob
        ,,,Bob
        20240301,20240201,MSFT,Bob
        20240101,,MSFT,
        20240301,20240201,,
        20240301,20240201,MSFT,
    """)
    assert [(row.is_noop, row.noop_reason) for row in patch.rows] == [
        (False, None),
        (True, NoOpRowReason.BLANK_KEY),
        (True, NoOpRowReason.REVERSED_DATES),
        (True, NoOpRowReason.NO_VALUES),
        # Several problems: the first reason in the order blank key, reversed dates, no values is reported
        (True, NoOpRowReason.BLANK_KEY),
        (True, NoOpRowReason.REVERSED_DATES),
    ]


def test_parser_drops_byte_order_mark_when_file_starts_with_one(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text("BeginDate,EndDate,Issuer,Analyst\n,,MSFT,Bob\n", encoding="utf-8-sig")
    patch = load_patch(path)
    assert patch.name == "bom.csv"
    assert patch.key_column == "Issuer"


def test_read_patch_text_returns_path_and_lines_with_line_breaks_when_file_is_read(tmp_path):
    path = tmp_path / "patch.csv"
    path.write_bytes(b"BeginDate,EndDate,Issuer,Analyst\r\n,,MSFT,Bob\n")
    assert read_patch_text(path) == PatchText(
        str(path),
        ("BeginDate,EndDate,Issuer,Analyst\r\n", ",,MSFT,Bob\n"),
    )


CZECH_LINES = ("BeginDate,EndDate,Issuer,Analyst\n", ",,CEZ,Dvořák\n")
CZECH_TEXT = "".join(CZECH_LINES)


def test_read_patch_text_reads_file_as_utf8_when_file_is_valid_utf8_whatever_the_local_encoding_is(
    tmp_path, monkeypatch
):
    path = tmp_path / "utf8.csv"
    path.write_bytes(CZECH_TEXT.encode("utf-8"))
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1250")
    assert read_patch_text(path).lines == CZECH_LINES


def test_read_patch_text_reads_file_in_given_encoding_when_encoding_is_given(tmp_path):
    path = tmp_path / "cp1250.csv"
    path.write_bytes(CZECH_TEXT.encode("cp1250"))
    assert read_patch_text(path, encoding="cp1250").lines == CZECH_LINES


def test_read_patch_text_reads_file_in_local_encoding_of_the_machine_when_file_is_not_valid_utf8(
    tmp_path, monkeypatch
):
    path = tmp_path / "cp1250.csv"
    path.write_bytes(CZECH_TEXT.encode("cp1250"))
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1250")
    assert read_patch_text(path).lines == CZECH_LINES


def test_read_patch_text_raises_error_naming_file_and_both_encodings_when_neither_utf8_nor_local_encoding_can_read_file(
    tmp_path, monkeypatch
):
    path = tmp_path / "broken.csv"
    # Byte 0x81 is not valid UTF-8, and cp1252 has no character for it
    path.write_bytes(b"BeginDate,EndDate,Issuer,Analyst\n,,MSFT,B\x81b\n")
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")
    with pytest.raises(PatchError) as error:
        read_patch_text(path)
    assert str(error.value) == (
        f"{path}: cannot read the file as UTF-8 or as cp1252 (the local encoding), "
        "use --encoding to name the encoding of the file"
    )


@pytest.mark.parametrize("local_encoding", ["utf-8", "UTF8", "utf-8-sig"])
def test_read_patch_text_does_not_try_utf8_twice_when_local_encoding_is_utf8_too(tmp_path, monkeypatch, local_encoding):
    path = tmp_path / "broken.csv"
    path.write_bytes(b"BeginDate,EndDate,Issuer,Analyst\n,,MSFT,B\x81b\n")
    monkeypatch.setattr(locale, "getencoding", lambda: local_encoding)
    with pytest.raises(PatchError) as error:
        read_patch_text(path)
    assert str(error.value) == (
        f"{path}: cannot read the file as UTF-8, use --encoding to name the encoding of the file"
    )


def test_read_patch_text_raises_error_naming_file_and_encoding_when_given_encoding_cannot_read_file(tmp_path):
    path = tmp_path / "cp1250.csv"
    path.write_bytes(CZECH_TEXT.encode("cp1250"))
    with pytest.raises(PatchError) as error:
        read_patch_text(path, encoding="ascii")
    assert str(error.value) == f"{path}: cannot read the file as ascii"


def test_read_patch_text_does_not_try_local_encoding_when_given_encoding_cannot_read_file(tmp_path, monkeypatch):
    path = tmp_path / "cp1250.csv"
    path.write_bytes(CZECH_TEXT.encode("cp1250"))
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1250")
    with pytest.raises(PatchError) as error:
        read_patch_text(path, encoding="utf-8")
    assert str(error.value) == f"{path}: cannot read the file as utf-8"


def test_read_patch_text_raises_error_when_given_encoding_name_is_unknown(tmp_path):
    path = tmp_path / "patch.csv"
    path.write_bytes(b"BeginDate,EndDate,Issuer,Analyst\n")
    with pytest.raises(PatchError) as error:
        read_patch_text(path, encoding="klingon")
    assert str(error.value) == f"{path}: unknown encoding 'klingon'"


@pytest.mark.parametrize("encoding", ["utf-8", "UTF8"])
def test_parser_drops_byte_order_mark_when_utf8_is_given_as_the_encoding(tmp_path, encoding):
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbfBeginDate,EndDate,Issuer,Analyst\n,,MSFT,Bob\n")
    assert read_patch_text(path, encoding=encoding).lines[0] == "BeginDate,EndDate,Issuer,Analyst\n"
    assert load_patch(path, encoding=encoding).key_column == "Issuer"


def test_parser_reads_cell_as_one_value_when_quoted_cell_runs_over_two_lines():
    patch = parse_patch(
        PatchText(
            "patch.csv",
            (
                "BeginDate,EndDate,Issuer,Comment\n",
                ',,MSFT,"first line\n',
                'second line"\n',
                ",,CAT,short\n",
            ),
        )
    )
    assert [(row.line, row.key, row.values) for row in patch.rows] == [
        (3, "MSFT", {"Comment": "first line\nsecond line"}),
        (4, "CAT", {"Comment": "short"}),
    ]


def test_parser_names_patch_after_the_path_when_given_patch_text():
    patch = parse_patch(PatchText("folder/old.csv", ("BeginDate,EndDate,Issuer,Analyst\n",)))
    assert patch.path == "folder/old.csv"
    assert patch.name == "old.csv"


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "the file is empty"),
        ("EndDate,Issuer,Analyst\n", "column 'BeginDate' is missing"),
        ("BeginDate,Issuer,Analyst\n", "column 'EndDate' is missing"),
        ("BeginDate,EndDate\n", "there is no key column"),
        ("BeginDate,EndDate,Issuer,Analyst,Analyst\n", "column 'Analyst' appears more than once"),
        ("BeginDate,EndDate,Issuer\n,,MSFT\n1/2/24,,CAT\n", "patch.csv, row 3: cannot read date '1/2/24'"),
        ("BeginDate,EndDate,Issuer\n,02/30/2024,MSFT\n", "patch.csv, row 2: '02/30/2024' is not a real date"),
        ("BeginDate,EndDate,Issuer\n,,MSFT,Bob\n", "patch.csv, row 2: value 'Bob' is in a column that has no name"),
        ("BeginDate,EndDate,Issuer,,Sector\n,,MSFT,Bob,\n", "value 'Bob' is in a column that has no name"),
    ],
)
def test_parser_raises_error_when_patch_is_malformed(make_patch, text, message):
    with pytest.raises(PatchError) as error:
        make_patch(text)
    assert message in str(error.value)
