"""Check the effect diff against a slow and simple model, for every pair of date ranges.

The model applies the rows of a patch one by one to every single day and writes down the
value the day ends up with. It knows nothing about timelines or splitting date ranges.
The effect diff must report exactly the days where the old and the new model disagree,
with the same values.

The ranges use four dates, and each side of a range can also be open. The days checked go
one day beyond those dates on both sides, so the open ends are covered too.
"""

from datetime import date, timedelta
from itertools import pairwise, product
from typing import Callable

import pytest

from patchdiff.diff import diff_patches
from patchdiff.model.patch_date import PatchDate
from patchdiff.model.patch_model import Patch

# A date range the way the model sees it: (begin, end), None means no limit
Dates = tuple[date | None, date | None]
# A row the way the model sees it: its dates and the value it sets
ModelRow = tuple[Dates, str]

HEADER = "BeginDate,EndDate,Issuer,Country\n"
DATES = [date(2024, 2, 27) + timedelta(days=offset) for offset in range(4)]  # Feb 27 to Mar 1, over the leap day
DAYS_TO_CHECK = [DATES[0] - timedelta(days=1), *DATES, DATES[-1] + timedelta(days=1)]

# Every range with a begin and an end taken from DATES or left open, the begin not after the end
RANGES: list[Dates] = [
    (begin, end)
    for begin, end in product([None, *DATES], repeat=2)
    if begin is None or end is None or begin <= end
]


def csv_row(dates: Dates, value: str) -> str:
    begin, end = dates
    begin_text = f"{begin:%Y%m%d}" if begin else ""
    end_text = f"{end.month}/{end.day}/{end.year}" if end else ""  # the other date format, on purpose
    return f"{begin_text},{end_text},BLA,{value}\n"


def value_on_day(rows: list[ModelRow], day: date) -> str | None:
    """The slow model: apply the rows in order to one day. Returns the value, or None if no row sets it."""
    value = None
    for (begin, end), row_value in rows:
        if (begin is None or begin <= day) and (end is None or day <= end):
            value = row_value
    return value


def check_effect_diffs_against_model(
    make_patch: Callable[..., Patch], old_rows: list[ModelRow], new_rows: list[ModelRow]
) -> None:
    old_text = HEADER + "".join(csv_row(dates, value) for dates, value in old_rows)
    new_text = HEADER + "".join(csv_row(dates, value) for dates, value in new_rows)
    effect_diffs = diff_patches(make_patch(old_text), make_patch(new_text)).effect_diffs

    for day in DAYS_TO_CHECK:
        diffs_on_day = [d for d in effect_diffs if d.dates.begin <= PatchDate(day) <= d.dates.end]
        old_value, new_value = value_on_day(old_rows, day), value_on_day(new_rows, day)
        if old_value == new_value:
            assert diffs_on_day == [], f"{day}: no difference expected"
        else:
            assert len(diffs_on_day) == 1, f"{day}: exactly one diff expected"
            [effect_diff] = diffs_on_day
            assert effect_diff.old_value == old_value, f"{day}: old value"
            assert effect_diff.new_value == new_value, f"{day}: new value"

    for previous, effect_diff in pairwise(effect_diffs):
        assert previous.dates.end < effect_diff.dates.begin, "diffs must be in date order and must not overlap"
        is_adjacent = previous.dates.end.next_day() == effect_diff.dates.begin
        has_same_values = (previous.old_value, previous.new_value) == (effect_diff.old_value, effect_diff.new_value)
        assert not (is_adjacent and has_same_values), "adjacent diffs with the same values must be merged"


@pytest.mark.parametrize("new_value", ["USA", "FRA"], ids=["different_value", "same_value"])
def test_effect_diff_matches_day_by_day_model_when_new_row_replaces_old_row(make_patch, new_value):
    for old_dates, new_dates in product(RANGES, repeat=2):
        check_effect_diffs_against_model(make_patch, [(old_dates, "FRA")], [(new_dates, new_value)])


@pytest.mark.parametrize("new_value", ["USA", "FRA"], ids=["different_value", "same_value"])
def test_effect_diff_matches_day_by_day_model_when_row_is_added_after_old_row(make_patch, new_value):
    for old_dates, added_dates in product(RANGES, repeat=2):
        old_rows = [(old_dates, "FRA")]
        check_effect_diffs_against_model(make_patch, old_rows, old_rows + [(added_dates, new_value)])


@pytest.mark.parametrize("new_value", ["USA", "FRA"], ids=["different_value", "same_value"])
def test_effect_diff_matches_day_by_day_model_when_row_is_added_before_old_row(make_patch, new_value):
    for old_dates, added_dates in product(RANGES, repeat=2):
        old_rows = [(old_dates, "FRA")]
        check_effect_diffs_against_model(make_patch, old_rows, [(added_dates, new_value)] + old_rows)


def test_effect_diff_matches_day_by_day_model_when_new_patch_sets_same_value_in_two_rows(make_patch):
    # Two rows with one value give the same difference on both sides of the cut between them.
    # This is the case where adjacent diffs must be merged into one.
    for old_dates, first_dates, second_dates in product(RANGES, repeat=3):
        old_rows = [(old_dates, "FRA")]
        new_rows = [(first_dates, "USA"), (second_dates, "USA")]
        check_effect_diffs_against_model(make_patch, old_rows, new_rows)


def test_effect_diff_matches_day_by_day_model_when_both_patches_have_two_overlapping_rows(make_patch):
    # A smaller set of ranges, so that four of them can be combined in every way
    ranges = [dates for dates in RANGES if dates[0] in (None, DATES[1]) and dates[1] in (None, DATES[1], DATES[2])]
    for first, second, third, fourth in product(ranges, repeat=4):
        old_rows = [(first, "FRA"), (second, "USA")]
        new_rows = [(third, "USA"), (fourth, "GER")]
        check_effect_diffs_against_model(make_patch, old_rows, new_rows)
