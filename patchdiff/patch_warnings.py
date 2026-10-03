"""Find things in one patch that look like a mistake.

A warning is about one patch on its own, not about the difference between two patches:

- a row that does nothing: blank key, BeginDate after EndDate, or no values
- a redundant row: later rows overwrite all its values on every date
- an empty column: it has no values

Two rows that set the same column on the same dates are not a warning, as long as the
earlier row still sets something. A value for all dates and another value from some
date on is the normal way to write a patch.
"""

from __future__ import annotations

from .effect import group_rows_by_key, ranges_overlap
from .model.effect_model import Effect
from .model.patch_model import Patch, PatchRow
from .model.warning_model import EmptyColumnWarning, NoOpRowWarning, PatchWarning, RedundantRowWarning


def find_warnings(patch: Patch, effect: Effect) -> list[PatchWarning]:
    """All warnings for one patch: row warnings in file order, then column warnings."""
    row_warnings: list[NoOpRowWarning | RedundantRowWarning] = [
        *_find_noop_rows(patch),
        *_find_redundant_rows(patch, effect),
    ]
    row_warnings.sort(key=lambda warning: warning.row.line)
    return [*row_warnings, *_find_empty_columns(patch)]


def _find_noop_rows(patch: Patch) -> list[NoOpRowWarning]:
    return [NoOpRowWarning(row) for row in patch.rows if row.is_noop]


def _find_redundant_rows(patch: Patch, effect: Effect) -> list[RedundantRowWarning]:
    """Rows that have no value left that causes changes: later rows overwrite every value on every date.

    The warning names the later rows that overwrite the row. A row that does nothing
    by itself is not redundant, it has its own warning.
    """
    rows_that_do_something = (row for row in patch.rows if not row.is_noop)
    warnings = []
    for rows in group_rows_by_key(rows_that_do_something).values():
        for position, row in enumerate(rows):
            if row.line not in effect.lines_of_effective_rows:
                later_rows = rows[position + 1 :]
                overridden_by = tuple(later_row for later_row in later_rows if _overwrites_some_value(later_row, row))
                warnings.append(RedundantRowWarning(row, overridden_by))
    return warnings


def _overwrites_some_value(later_row: PatchRow, row: PatchRow) -> bool:
    """True if the later row, of the same key, sets a column that `row` sets and shares a date with it."""
    return any(column in row.values for column in later_row.values) and ranges_overlap(row.dates, later_row.dates)


def _find_empty_columns(patch: Patch) -> list[EmptyColumnWarning]:
    """Columns that have no values, in the column order of the patch."""
    columns_with_values = {column for row in patch.rows for column in row.values}
    return [EmptyColumnWarning(column) for column in patch.value_columns if column not in columns_with_values]
