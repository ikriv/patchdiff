"""PatchDate and DateRange: the two date types of the model."""

import copy
from datetime import date

import pytest

from patchdiff.model.patch_date import INFINITE_FUTURE, INFINITE_PAST, PatchDate
from patchdiff.model.patch_model import DateRange


def test_patch_dates_put_infinite_past_first_and_infinite_future_last_when_sorted():
    january = PatchDate(date(2024, 1, 10))
    february = PatchDate(date(2024, 2, 1))
    assert INFINITE_PAST < january < february < INFINITE_FUTURE
    assert INFINITE_FUTURE > february >= january > INFINITE_PAST
    assert january == PatchDate(date(2024, 1, 10))
    assert january != february
    assert not INFINITE_PAST < INFINITE_PAST
    assert not INFINITE_FUTURE < INFINITE_FUTURE
    assert INFINITE_PAST != INFINITE_FUTURE
    assert copy.deepcopy(INFINITE_PAST) == INFINITE_PAST
    assert repr(INFINITE_FUTURE) == "PatchDate(value=<_Infinite.FUTURE: 'future'>)"
    assert INFINITE_FUTURE <= INFINITE_FUTURE
    with pytest.raises(TypeError):
        january < date(2024, 1, 10)  # type: ignore[operator]
    assert sorted({INFINITE_FUTURE, february, INFINITE_PAST, january, PatchDate(date(2024, 1, 10))}) == [
        INFINITE_PAST,
        january,
        february,
        INFINITE_FUTURE,
    ]


def test_patch_date_moves_one_day_when_real_and_stays_put_when_infinite():
    january_10 = PatchDate(date(2024, 1, 10))
    assert january_10.next_day() == PatchDate(date(2024, 1, 11))
    assert january_10.previous_day() == PatchDate(date(2024, 1, 9))
    assert PatchDate(date(2024, 2, 29)).next_day() == PatchDate(date(2024, 3, 1))
    assert INFINITE_PAST.next_day() == INFINITE_PAST
    assert INFINITE_PAST.previous_day() == INFINITE_PAST
    assert INFINITE_FUTURE.next_day() == INFINITE_FUTURE
    assert INFINITE_FUTURE.previous_day() == INFINITE_FUTURE
    # There are no days beyond the first and the last possible date
    assert PatchDate(date.max).next_day() == INFINITE_FUTURE
    assert PatchDate(date.min).previous_day() == INFINITE_PAST


def test_date_range_has_no_limits_when_built_without_dates_and_is_reversed_when_begin_is_after_end():
    all_dates = DateRange()
    assert (all_dates.begin, all_dates.end) == (INFINITE_PAST, INFINITE_FUTURE)
    assert (all_dates.first_day, all_dates.last_day) == (None, None)
    assert DateRange.from_dates(None, None) == all_dates

    january = DateRange.from_dates(date(2024, 1, 1), date(2024, 1, 31))
    assert january == DateRange(PatchDate(date(2024, 1, 1)), PatchDate(date(2024, 1, 31)))
    assert (january.first_day, january.last_day) == (date(2024, 1, 1), date(2024, 1, 31))
    assert not january.is_reversed
    assert not all_dates.is_reversed
    assert not DateRange.from_dates(date(2024, 1, 1), date(2024, 1, 1)).is_reversed
    assert DateRange.from_dates(date(2024, 1, 2), date(2024, 1, 1)).is_reversed
