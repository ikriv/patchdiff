"""Data model: a date that can also be infinitely far in the past or in the future."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from functools import total_ordering

ONE_DAY = timedelta(days=1)


class _Infinite(Enum):
    PAST = "past"
    FUTURE = "future"


@total_ordering
@dataclass(frozen=True)
class PatchDate:
    """A point on the date axis: a real date, INFINITE_PAST or INFINITE_FUTURE.

    Patch dates can be compared and sorted. INFINITE_PAST is before every real date,
    INFINITE_FUTURE is after every real date.
    """

    value: date | _Infinite

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PatchDate):
            return NotImplemented
        if isinstance(self.value, _Infinite):
            # The past is before everything except itself. The future is before nothing.
            return self.value == _Infinite.PAST and self != other
        if isinstance(other.value, _Infinite):
            return other.value == _Infinite.FUTURE
        return self.value < other.value

    def next_day(self) -> PatchDate:
        """The day after. An infinite date stays as it is."""
        if isinstance(self.value, _Infinite):
            return self
        if self.value == date.max:
            return INFINITE_FUTURE
        return PatchDate(self.value + ONE_DAY)

    def previous_day(self) -> PatchDate:
        """The day before. An infinite date stays as it is."""
        if isinstance(self.value, _Infinite):
            return self
        if self.value == date.min:
            return INFINITE_PAST
        return PatchDate(self.value - ONE_DAY)


INFINITE_PAST = PatchDate(_Infinite.PAST)
INFINITE_FUTURE = PatchDate(_Infinite.FUTURE)
