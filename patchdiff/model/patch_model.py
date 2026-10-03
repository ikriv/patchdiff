"""Data model: a patch file and its rows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
from typing import Mapping

from .patch_date import INFINITE_FUTURE, INFINITE_PAST, PatchDate


# The name of a column. It is a plain string, the alias makes type hints easier to read.
ColumnName = str

# The two columns every patch has. They say on which dates a row applies.
BEGIN_DATE: ColumnName = "BeginDate"
END_DATE: ColumnName = "EndDate"


class PatchError(Exception):
    """Bad input: a file that is not a valid patch, or two patches that cannot be compared."""


@dataclass(frozen=True)
class DateRange:
    """A stretch of dates, both ends included. By default it is all dates."""

    begin: PatchDate = INFINITE_PAST
    end: PatchDate = INFINITE_FUTURE

    @classmethod
    def from_dates(cls, first_day: date | None, last_day: date | None) -> DateRange:
        """Build a range from two dates. None means no limit on that side."""
        # date.min and date.max also count as "no limit", there are no days beyond them
        begin = INFINITE_PAST if first_day is None or first_day == date.min else PatchDate(first_day)
        end = INFINITE_FUTURE if last_day is None or last_day == date.max else PatchDate(last_day)
        return cls(begin, end)

    @property
    def first_day(self) -> date | None:
        """The first day as a date, or None if the range has no begin."""
        return self.begin.value if isinstance(self.begin.value, date) else None

    @property
    def last_day(self) -> date | None:
        """The last day as a date, or None if the range has no end."""
        return self.end.value if isinstance(self.end.value, date) else None

    @property
    def is_reversed(self) -> bool:
        """True if the begin is after the end, so the range covers no dates."""
        return self.begin > self.end


class NoOpRowReason(Enum):
    """Why a row cannot change any data."""

    BLANK_KEY = auto()
    REVERSED_DATES = auto()  # BeginDate is after EndDate
    NO_VALUES = auto()


@dataclass(frozen=True)
class PatchRow:
    """One data row of a patch file."""

    line: int                      # line number in the file, the header is line 1
    key: str
    dates: DateRange
    values: Mapping[ColumnName, str]  # value column -> value, blank cells are left out

    @property
    def noop_reason(self) -> NoOpRowReason | None:
        """Why the row cannot change any data, or None if it can.

        A row with more than one problem gets the first reason: blank key, then reversed
        dates, then no values.
        """
        if not self.key:
            return NoOpRowReason.BLANK_KEY
        if self.dates.is_reversed:
            return NoOpRowReason.REVERSED_DATES
        if not self.values:
            return NoOpRowReason.NO_VALUES
        return None

    @property
    def is_noop(self) -> bool:
        """True if the row cannot change any data."""
        return self.noop_reason is not None


@dataclass(frozen=True)
class PatchText:
    """The lines of a patch file as they were read, and the path they were read from.

    The path only names the patch in the report and in error messages. Nothing reads from it.
    """

    file_path: str
    lines: tuple[str, ...]  # with their line breaks


@dataclass(frozen=True)
class Patch:
    """A parsed patch file."""

    path: str
    key_column: ColumnName
    value_columns: tuple[ColumnName, ...]  # in file order
    rows: tuple[PatchRow, ...]             # in file order

    @property
    def name(self) -> str:
        return os.path.basename(self.path)
