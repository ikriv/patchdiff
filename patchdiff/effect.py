"""The effect of a patch: which value each key and column gets on which dates.

Rows of a patch are applied top to bottom, so a later row wins over an earlier one.
For every key and value column we build a timeline: date ranges that do not overlap,
each with the value that wins there. Two patches have the same effect when their
timelines give the same value on every date.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Iterable

from .model.effect_model import Effect, ValueUpdate, ValueUpdatesTimeline
from .model.patch_date import PatchDate
from .model.patch_model import ColumnName, DateRange, Patch, PatchRow


def build_effect(patch: Patch) -> Effect:
    """Work out what the patch does: a timeline for every key and column it sets."""
    timelines_per_key: dict[str, dict[ColumnName, ValueUpdatesTimeline]] = {}
    effective_lines: set[int] = set()
    for key, rows in group_rows_by_key(patch.rows).items():
        timelines: dict[ColumnName, ValueUpdatesTimeline] = {}
        for column in patch.value_columns:
            winning_rows = find_winning_rows(rows, column)
            if winning_rows:
                timelines[column] = build_timeline(winning_rows, column)
                effective_lines.update(row.line for _, row in winning_rows)
        if timelines:
            timelines_per_key[key] = timelines
    return Effect(timelines_per_key, frozenset(effective_lines))


def group_rows_by_key(rows: Iterable[PatchRow]) -> dict[str, list[PatchRow]]:
    """The rows of every key, in the order given."""
    rows_by_key: dict[str, list[PatchRow]] = {}
    for row in rows:
        rows_by_key.setdefault(row.key, []).append(row)
    return rows_by_key


def find_winning_rows(rows: list[PatchRow], column: ColumnName) -> list[tuple[DateRange, PatchRow]]:
    """Cut the dates into stretches, and for every stretch find the row that sets the column there.

    The rows are the rows of one key in file order. Returns the stretches in date order.
    A stretch that no row covers is left out.
    """
    rows = [row for row in rows if column in row.values and not row.is_noop]
    winning_rows = []
    for dates in split_into_non_overlapping_ranges(row.dates for row in rows):
        # A later row overrides an earlier one, so the last row that covers the stretch wins
        winner = next((row for row in reversed(rows) if range_contains(row.dates, dates)), None)
        if winner is not None:
            winning_rows.append((dates, winner))
    return winning_rows


def build_timeline(winning_rows: list[tuple[DateRange, PatchRow]], column: ColumnName) -> ValueUpdatesTimeline:
    """The values of one column in date order, from the winning rows of one key.

    Stretches that follow each other with no gap and have the same value are joined
    into one update, whether the value comes from one row or from several.
    """
    timeline: list[ValueUpdate] = []
    for dates, row in winning_rows:
        value = row.values[column]
        last = timeline[-1] if timeline else None
        if last and last.value == value and starts_day_after(dates, last.dates):
            timeline[-1] = ValueUpdate(DateRange(last.dates.begin, dates.end), value)
        else:
            timeline.append(ValueUpdate(dates, value))
    return tuple(timeline)


def split_into_non_overlapping_ranges(ranges: Iterable[DateRange]) -> list[DateRange]:
    """Cut the date axis at the begin and the end of every given range.

    Returns the stretches between the cuts, in date order. Inside one stretch nothing
    changes: each of the given ranges covers it fully or not at all.
    """
    # Every range begins a stretch, and the day after it ends begins another one
    begins = sorted({begin for dates in ranges for begin in (dates.begin, dates.end.next_day())})
    return [DateRange(begin, next_begin.previous_day()) for begin, next_begin in pairwise(begins)]


def range_contains(outer: DateRange, inner: DateRange) -> bool:
    """True if every date of `inner` is also in `outer`."""
    return outer.begin <= inner.begin and inner.end <= outer.end


def starts_day_after(dates: DateRange, previous: DateRange) -> bool:
    """True if `dates` begins on the day after `previous` ends."""
    return previous.end.next_day() == dates.begin


def ranges_overlap(first: DateRange, second: DateRange) -> bool:
    """True if at least one date is in both ranges."""
    return first.begin <= second.end and second.begin <= first.end


def find_value_on_day(timeline: ValueUpdatesTimeline, day: PatchDate) -> str | None:
    """The value on the given day, or None if the column is not set on that day."""
    for update in timeline:
        if update.dates.begin <= day <= update.dates.end:
            return update.value
    return None
