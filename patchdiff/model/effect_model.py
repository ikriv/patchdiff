"""Data model: the effect of a patch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .patch_model import ColumnName, DateRange


@dataclass(frozen=True)
class ValueUpdate:
    """A stretch of dates where a patch sets one column to one value."""

    dates: DateRange
    value: str


# The value updates of one key and one column, in date order. They do not overlap,
# and two updates that follow each other with no gap have different values.
# It is a tuple, so it cannot be changed after it is built.
ValueUpdatesTimeline = tuple[ValueUpdate, ...]


@dataclass(frozen=True)
class Effect:
    """What a patch does: a timeline for every key and column the patch sets."""

    # key -> column -> timeline, no empty entries
    timelines_per_key_and_column: Mapping[str, Mapping[ColumnName, ValueUpdatesTimeline]]
    # Lines of the rows that have a value that causes changes: the value is what
    # the patch sets for some column on at least one date
    lines_of_effective_rows: frozenset[int]

    def get_timeline(self, key: str, column: ColumnName) -> ValueUpdatesTimeline:
        """Timeline of one column for one key. Empty if the patch does not set it."""
        return self.timelines_per_key_and_column.get(key, {}).get(column, ())
