"""Read a patch CSV file into a Patch."""

from __future__ import annotations

import codecs
import csv
import locale
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

from .model.patch_model import (
    BEGIN_DATE,
    END_DATE,
    ColumnName,
    DateRange,
    Patch,
    PatchError,
    PatchRow,
    PatchText,
)

_COMPACT_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})")
_DASHED_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_US_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Reads UTF-8 and drops the byte order mark that Excel puts at the start of a CSV file.
_UTF8_SIG = "utf-8-sig"


def parse_date(text: str) -> date | None:
    """Parse MM/DD/YYYY, YYYYMMDD or YYYY-MM-DD. Blank gives None. The machine locale is never used.

    Raises ValueError if the text is not a date.
    """
    if not text:
        return None
    if match := _COMPACT_DATE.fullmatch(text) or _DASHED_DATE.fullmatch(text):
        year, month, day = match.groups()
    elif match := _US_DATE.fullmatch(text):
        month, day, year = match.groups()
    else:
        raise ValueError(f"cannot read date '{text}', expected MM/DD/YYYY, YYYYMMDD or YYYY-MM-DD")
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        raise ValueError(f"'{text}' is not a real date") from None


def load_patch(path: str | Path, *, encoding: str | None = None) -> Patch:
    """Read and parse the patch file at the given path. See read_patch_text for the encoding."""
    return parse_patch(read_patch_text(path, encoding=encoding))


def read_patch_text(path: str | Path, *, encoding: str | None = None) -> PatchText:
    """Read the lines of a patch file. Nothing is parsed yet.

    If an encoding is given, the file is read in that encoding and no other.

    If no encoding is given, the file is read as UTF-8. A file that is not valid UTF-8
    is read again in the local encoding of the machine. Excel saves a plain CSV file
    in that encoding.

    Raises PatchError if the file cannot be read in the encodings above.
    """
    if encoding is not None:
        lines = _read_lines_in_given_encoding(path, encoding)
    else:
        lines = _read_lines_as_utf8_or_in_local_encoding(path)
    return PatchText(str(path), lines)


def _read_lines_in_given_encoding(path: str | Path, encoding: str) -> tuple[str, ...]:
    try:
        # A file that is said to be UTF-8 can still start with a byte order mark.
        # "utf8", "UTF-8" and "U8" are all names of UTF-8, so compare the standard name.
        is_utf8 = codecs.lookup(encoding).name == "utf-8"
        return _read_lines(path, _UTF8_SIG if is_utf8 else encoding)
    except LookupError:
        raise PatchError(f"{path}: unknown encoding '{encoding}'") from None
    except UnicodeDecodeError:
        raise PatchError(f"{path}: cannot read the file as {encoding}") from None


def _read_lines_as_utf8_or_in_local_encoding(path: str | Path) -> tuple[str, ...]:
    try:
        return _read_lines(path, _UTF8_SIG)
    except UnicodeDecodeError:
        pass
    # Not getpreferredencoding(): it says "utf-8" when Python runs in UTF-8 mode,
    # whatever the encoding of the machine is.
    local_encoding = locale.getencoding()
    how_to_fix = "use --encoding to name the encoding of the file"
    if _is_utf8(local_encoding):
        # The local encoding is UTF-8 as well, as on most Linux and Mac machines. No second try.
        raise PatchError(f"{path}: cannot read the file as UTF-8, {how_to_fix}")
    try:
        return _read_lines(path, local_encoding)
    except (UnicodeDecodeError, LookupError):
        raise PatchError(
            f"{path}: cannot read the file as UTF-8 or as {local_encoding} (the local encoding), {how_to_fix}"
        ) from None


def _is_utf8(encoding: str) -> bool:
    """True if the name is one of the names of UTF-8: "utf8", "UTF-8", "U8", "utf-8-sig" and so on."""
    try:
        return codecs.lookup(encoding).name in ("utf-8", "utf-8-sig")
    except LookupError:
        return False


def _read_lines(path: str | Path, encoding: str) -> tuple[str, ...]:
    # newline="" keeps the line breaks as they are. The csv module needs them
    # to read a quoted cell that runs over two lines.
    with open(path, newline="", encoding=encoding) as file:
        return tuple(file)


def parse_patch(patch_text: PatchText) -> Patch:
    """Parse the lines of a patch file into a Patch."""
    path = patch_text.file_path
    reader = csv.reader(patch_text.lines)
    # A quoted cell can run over several lines, so the number of a row is the line the reader is on
    numbered_rows = ((reader.line_num, cells) for cells in reader)
    try:
        return _parse(numbered_rows, path)
    except csv.Error as error:
        raise PatchError(f"{path}, row {reader.line_num}: not a valid CSV file: {error}") from None


def _parse(numbered_rows: Iterator[tuple[int, list[str]]], path: str) -> Patch:
    """Build a Patch from the rows of the file, each with its line number. The first row is the header."""
    first_row = next(numbered_rows, None)
    if first_row is None:
        raise PatchError(f"{path}: the file is empty")
    _, header = first_row
    columns = _parse_header(header, path)
    rows = (_parse_row(line, cells, columns, path) for line, cells in numbered_rows)
    return Patch(path, columns.key_column, columns.value_columns, tuple(row for row in rows if row is not None))


@dataclass(frozen=True)
class _Columns:
    """What the header says: the columns by position, which one is the key and which ones hold values."""

    names: list[ColumnName]  # by position, "" for a column with no name
    position: dict[ColumnName, int]
    key_column: ColumnName
    value_columns: tuple[ColumnName, ...]


def _parse_header(header: list[str], path: str) -> _Columns:
    names = [name.strip() for name in header]
    position: dict[ColumnName, int] = {}
    for index, name in enumerate(names):
        if not name:
            continue
        if name in position:
            raise PatchError(f"{path}: column '{name}' appears more than once")
        position[name] = index
    for required in (BEGIN_DATE, END_DATE):
        if required not in position:
            raise PatchError(f"{path}: column '{required}' is missing")
    other_columns = [name for name in names if name and name not in (BEGIN_DATE, END_DATE)]
    if not other_columns:
        raise PatchError(f"{path}: there is no key column")
    return _Columns(names, position, other_columns[0], tuple(other_columns[1:]))


def _parse_row(line: int, cells: list[str], columns: _Columns, path: str) -> PatchRow | None:
    """One data row. None if every cell is blank: such a line is skipped."""
    cells = [cell.strip() for cell in cells]
    if not any(cells):
        return None
    for index, cell in enumerate(cells):
        if cell and (index >= len(columns.names) or not columns.names[index]):
            raise PatchError(f"{path}, row {line}: value '{cell}' is in a column that has no name")
    # A short row has blank cells at the end
    cells += [""] * (len(columns.names) - len(cells))
    position = columns.position

    try:
        dates = DateRange.from_dates(parse_date(cells[position[BEGIN_DATE]]), parse_date(cells[position[END_DATE]]))
    except ValueError as error:
        raise PatchError(f"{path}, row {line}: {error}") from None
    values = {column: cells[position[column]] for column in columns.value_columns if cells[position[column]]}
    return PatchRow(line, cells[position[columns.key_column]], dates, values)
