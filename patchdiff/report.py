"""Turn a PatchDiff into plain text."""

from __future__ import annotations

from datetime import date
from itertools import chain, groupby
from typing import Sequence

from .model.diff_model import EffectDiff, PatchDiff
from .model.patch_model import BEGIN_DATE, END_DATE, ColumnName, DateRange, NoOpRowReason, PatchRow
from .model.warning_model import EmptyColumnWarning, NoOpRowWarning, PatchWarning, RedundantRowWarning

INDENT = "    "

OLD = "Old"  # how the report calls the old patch
NEW = "New"  # and the new patch

NO_DIFFERENCES = "No differences: the two patches do the same thing."


def render_diff(diff: PatchDiff, *, with_warnings: bool = True) -> str:
    """The report: the file names, the differences and the warnings.

    The warnings part is left out if there are no warnings, or if the caller does not
    want them. Each part is rendered on its own and ends with a line break. The parts
    are put together with one blank line between them.
    """
    parts = [render_title(diff), render_differences(diff)]
    if with_warnings and (diff.old_warnings or diff.new_warnings):
        parts.append(render_warnings(diff))
    return "\n".join(parts)


def render_title(diff: PatchDiff) -> str:
    """Which file is the old patch and which is the new one."""
    return _text([f"{OLD}: {diff.old_name}", f"{NEW}: {diff.new_name}"])


def render_differences(diff: PatchDiff) -> str:
    """Removed and added columns, then what the new patch adds, removes and changes for every key.

    If there is nothing to list, one line says so.
    """
    columns = _column_lines(diff)
    changes = _change_lines(diff)
    if not columns and not changes:
        return _text([NO_DIFFERENCES])
    blank_line = [""] if columns and changes else []
    return _text([*columns, *blank_line, *changes])


def render_warnings(diff: PatchDiff) -> str:
    """The warnings section: things that look like a mistake, for each patch on its own.

    The warnings of a patch are indented under its name. A patch that has no warnings is left out.
    If neither patch has warnings, render_diff leaves the whole section out.
    """
    lines = ["WARNINGS", ""]
    for side, warnings in ((OLD, diff.old_warnings), (NEW, diff.new_warnings)):
        if warnings:
            lines += [f"{side} Patch:", *_indented(_warning_lines(diff.key_column, warnings)), ""]
    return _text(lines)


def quote(value: str) -> str:
    """A value from a patch file in single quotes, on one line.

    The quotes show where the value begins and ends, so a value with a comma in it
    cannot be misread, and an empty value can be seen.
    """
    return "'" + value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ") + "'"


def _text(lines: list[str]) -> str:
    """Lines as one text that ends with exactly one line break."""
    return "\n".join(lines).rstrip("\n") + "\n"


def _indented(lines: list[str]) -> list[str]:
    return [INDENT + line for line in lines]


def _name_value_pair(name: str, value: str) -> str:
    return f"{name}={quote(value)}"


def _date(day: date) -> str:
    """A date as YYYY-MM-DD, whatever format the file has it in."""
    return day.isoformat()


def _date_range(dates: DateRange) -> tuple[str, ...]:
    """The begin and the end of a date range as name=date pairs. A side with no limit is left out."""
    begin = (f"{BEGIN_DATE}={_date(dates.first_day)}",) if dates.first_day else ()
    end = (f"{END_DATE}={_date(dates.last_day)}",) if dates.last_day else ()
    return begin + end


def _date_range_in_words(dates: DateRange) -> str:
    """A date range the way one would say it. Empty if the range is all dates.

    'for 2024-01-15', 'for dates between 2024-01-10 and 2024-01-20',
    'for dates on or after 2024-01-10', 'for dates on or before 2024-01-20'.
    """
    first_day, last_day = dates.first_day, dates.last_day
    if first_day and first_day == last_day:
        return f"for {_date(first_day)}"
    if first_day and last_day:
        return f"for dates between {_date(first_day)} and {_date(last_day)}"
    if first_day:
        return f"for dates on or after {_date(first_day)}"
    if last_day:
        return f"for dates on or before {_date(last_day)}"
    return ""


def _column_lines(diff: PatchDiff) -> list[str]:
    """One line for every column that is in one patch only: removed columns, then added columns."""
    removed = [f"Removed column {column}" for column in diff.columns_only_in_old]
    added = [f"Added column {column}" for column in diff.columns_only_in_new]
    return removed + added


def _change_lines(diff: PatchDiff) -> list[str]:
    """The changes of every key. A key with one change takes one line, a key with more has one line per change.

    The key line says whether the new patch started or stopped patching the key, or modified it.

    Modified Issuer 'MSFT': Changed Analyst from 'Bob' to 'Mike'
    Now patching Issuer 'IRM':
        Added Analyst 'Emily' for dates on or before 2025-03-11
        Added Sector 'Real Estate' for 2025-01-12
    """
    lines = []
    for key, effect_diffs in groupby(diff.effect_diffs, key=lambda effect_diff: effect_diff.key):
        changes = [_change(effect_diff) for effect_diff in effect_diffs]
        key_header = f"{_key_change(diff, key)} {diff.key_column} {quote(key)}:"
        if len(changes) == 1:
            lines.append(f"{key_header} {changes[0]}")
        else:
            lines += [key_header, *_indented(changes)]
    return lines


def _key_change(diff: PatchDiff, key: str) -> str:
    """What happened to the key: the new patch sets values for it and the old one did not, the other way round, or both do."""
    if key in diff.keys_only_in_new:
        return "Now patching"
    if key in diff.keys_only_in_old:
        return "No longer patching"
    return "Modified"


def _change(effect_diff: EffectDiff) -> str:
    """What the new patch does to one column of one key: adds a value, removes it or changes it. Then the dates."""
    column = effect_diff.column
    match effect_diff.old_value, effect_diff.new_value:
        case None, str() as new_value:
            change = f"Added {column} {quote(new_value)}"
        case str() as old_value, None:
            change = f"Removed {column} {quote(old_value)}"
        case str() as old_value, str() as new_value:
            change = f"Changed {column} from {quote(old_value)} to {quote(new_value)}"
        case _:
            raise ValueError(f"column {column} has no value in either patch, this is not a difference")
    dates_in_words = _date_range_in_words(effect_diff.dates)
    return f"{change} {dates_in_words}" if dates_in_words else change


def _warning_lines(key_column: ColumnName, warnings: Sequence[PatchWarning]) -> list[str]:
    """The warnings of one patch. Under a row warning, indented, the rows it is about."""
    lines = []
    for warning in warnings:
        lines.append(_warning_text(key_column, warning))
        lines += _indented([_cited_row(key_column, row) for row in _rows_of_warning(warning)])
    return lines


def _warning_text(key_column: ColumnName, warning: PatchWarning) -> str:
    match warning:
        case NoOpRowWarning():
            return f"Row {warning.row.line}: {_noop_row_reason(key_column, warning.row)}, the row does nothing"
        case RedundantRowWarning():
            later_rows = _row_numbers(warning.overridden_by)
            overwrite = "overwrites" if len(warning.overridden_by) == 1 else "overwrite"
            return f"Row {warning.row.line}: redundant, {later_rows} {overwrite} all its values"
        case EmptyColumnWarning():
            return f"Column {warning.column} has no values and therefore does nothing"


def _rows_of_warning(warning: PatchWarning) -> list[PatchRow]:
    """The rows a warning is about, to print under it. A column warning has none."""
    match warning:
        case NoOpRowWarning():
            return [warning.row]
        case RedundantRowWarning():
            return [warning.row, *warning.overridden_by]
        case EmptyColumnWarning():
            return []


def _noop_row_reason(key_column: ColumnName, row: PatchRow) -> str:
    match row.noop_reason:
        case NoOpRowReason.BLANK_KEY:
            return f"{key_column} is blank"
        case NoOpRowReason.REVERSED_DATES:
            # Reversed dates are always two real dates
            begin, end = _date_range(row.dates)
            return f"{begin} is after {end}"
        case NoOpRowReason.NO_VALUES:
            return "no values"
        case None:
            raise ValueError(f"row {row.line} does something, it is not a no-op row")


def _row_numbers(rows: tuple[PatchRow, ...]) -> str:
    """'row 6', 'rows 6 and 8', 'rows 6, 8 and 9'."""
    lines = [str(row.line) for row in rows]
    if len(lines) == 1:
        return f"row {lines[0]}"
    return f"rows {', '.join(lines[:-1])} and {lines[-1]}"


def _cited_row(key_column: ColumnName, row: PatchRow) -> str:
    """A whole row with its key, the way the file has it."""
    key = (_name_value_pair(key_column, row.key),)
    values = (_name_value_pair(column, value) for column, value in row.values.items())
    pairs = chain(key, _date_range(row.dates), values)
    empty = "" if row.values else " (all empty)"
    return f"row {row.line}: {', '.join(pairs)}{empty}"
