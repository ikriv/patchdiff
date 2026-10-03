"""How the effect diff handles rows whose dates overlap in every possible way.

The input is CSV text and goes through the real parser. The output is the diff data,
so no report wording is involved. Every test uses one key and one column. The old patch
has the row `OLD_ROW`, from January 10 to January 20, unless the test says otherwise.

An effect diff is written here as (first day, last day, old value, new value).
None as a day means no limit on that side. None as a value means the patch does
not set the column on those dates.
"""

from datetime import date
from typing import Callable

from patchdiff.diff import diff_patches
from patchdiff.model.patch_model import Patch

HEADER = "BeginDate,EndDate,Issuer,Country\n"
OLD_ROW = "1/10/2024,1/20/2024,BLA,FRA\n"

# (first day, last day, old value, new value)
EffectDiffSummary = tuple[date | None, date | None, str | None, str | None]


def january(day: int) -> date:
    return date(2024, 1, day)


def effect_diffs(make_patch: Callable[..., Patch], old_rows: str, new_rows: str) -> list[EffectDiffSummary]:
    diff = diff_patches(make_patch(HEADER + old_rows), make_patch(HEADER + new_rows))
    return [
        (effect_diff.dates.first_day, effect_diff.dates.last_day, effect_diff.old_value, effect_diff.new_value)
        for effect_diff in diff.effect_diffs
    ]


# ---- the new patch has one row in place of the old one


def test_new_row_replaces_old_row_on_all_dates_when_new_row_has_no_dates(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, ",,BLA,USA\n") == [
        (None, january(9), None, "USA"),
        (january(10), january(20), "FRA", "USA"),
        (january(21), None, None, "USA"),
    ]


def test_new_row_replaces_old_row_on_all_dates_when_new_dates_contain_old_dates(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/5/2024,1/25/2024,BLA,USA\n") == [
        (january(5), january(9), None, "USA"),
        (january(10), january(20), "FRA", "USA"),
        (january(21), january(25), None, "USA"),
    ]


def test_new_row_replaces_first_part_of_old_row_when_it_has_only_end_date_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, ",1/15/2024,BLA,USA\n") == [
        (None, january(9), None, "USA"),
        (january(10), january(15), "FRA", "USA"),
        (january(16), january(20), "FRA", None),
    ]


def test_new_row_replaces_last_part_of_old_row_when_it_has_only_begin_date_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/15/2024,,BLA,USA\n") == [
        (january(10), january(14), "FRA", None),
        (january(15), january(20), "FRA", "USA"),
        (january(21), None, None, "USA"),
    ]


def test_new_row_replaces_first_part_of_old_row_when_it_begins_before_and_ends_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/5/2024,1/15/2024,BLA,USA\n") == [
        (january(5), january(9), None, "USA"),
        (january(10), january(15), "FRA", "USA"),
        (january(16), january(20), "FRA", None),
    ]


def test_new_row_replaces_last_part_of_old_row_when_it_begins_in_the_middle_and_ends_after(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/15/2024,1/25/2024,BLA,USA\n") == [
        (january(10), january(14), "FRA", None),
        (january(15), january(20), "FRA", "USA"),
        (january(21), january(25), None, "USA"),
    ]


def test_new_row_replaces_middle_part_of_old_row_when_it_begins_and_ends_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/13/2024,1/17/2024,BLA,USA\n") == [
        (january(10), january(12), "FRA", None),
        (january(13), january(17), "FRA", "USA"),
        (january(18), january(20), "FRA", None),
    ]


def test_new_row_replaces_last_day_of_old_row_when_it_begins_on_the_day_old_row_ends(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/20/2024,1/30/2024,BLA,USA\n") == [
        (january(10), january(19), "FRA", None),
        (january(20), january(20), "FRA", "USA"),
        (january(21), january(30), None, "USA"),
    ]


def test_new_row_replaces_first_day_of_old_row_when_it_ends_on_the_day_old_row_begins(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/1/2024,1/10/2024,BLA,USA\n") == [
        (january(1), january(9), None, "USA"),
        (january(10), january(10), "FRA", "USA"),
        (january(11), january(20), "FRA", None),
    ]


def test_new_row_replaces_one_day_of_old_row_when_it_begins_and_ends_on_the_same_day(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/15/2024,1/15/2024,BLA,USA\n") == [
        (january(10), january(14), "FRA", None),
        (january(15), january(15), "FRA", "USA"),
        (january(16), january(20), "FRA", None),
    ]


def test_rows_share_no_day_when_new_row_begins_on_the_day_after_old_row_ends(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/21/2024,1/30/2024,BLA,USA\n") == [
        (january(10), january(20), "FRA", None),
        (january(21), january(30), None, "USA"),
    ]


def test_gap_day_is_in_no_diff_when_new_row_begins_two_days_after_old_row_ends(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/22/2024,1/30/2024,BLA,USA\n") == [
        (january(10), january(20), "FRA", None),
        (january(22), january(30), None, "USA"),
    ]


def test_one_diff_covers_all_dates_of_the_row_when_only_the_value_changes(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/10/2024,1/20/2024,BLA,USA\n") == [
        (january(10), january(20), "FRA", "USA"),
    ]


def test_no_diff_is_reported_when_new_row_has_same_dates_and_same_value(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/10/2024,1/20/2024,BLA,FRA\n") == []


def test_only_dates_outside_old_row_differ_when_new_row_is_wider_and_has_same_value(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/5/2024,1/25/2024,BLA,FRA\n") == [
        (january(5), january(9), None, "FRA"),
        (january(21), january(25), None, "FRA"),
    ]


def test_only_dates_outside_new_row_differ_when_new_row_is_narrower_and_has_same_value(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/13/2024,1/17/2024,BLA,FRA\n") == [
        (january(10), january(12), "FRA", None),
        (january(18), january(20), "FRA", None),
    ]


def test_new_row_replaces_middle_part_when_old_row_has_no_dates(make_patch):
    assert effect_diffs(make_patch, ",,BLA,FRA\n", "1/10/2024,1/20/2024,BLA,USA\n") == [
        (None, january(9), "FRA", None),
        (january(10), january(20), "FRA", "USA"),
        (january(21), None, "FRA", None),
    ]


# ---- the new patch keeps the old row and adds a second row after it


def test_added_row_overrides_old_row_on_all_dates_when_added_row_has_no_dates(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + ",,BLA,USA\n") == [
        (None, january(9), None, "USA"),
        (january(10), january(20), "FRA", "USA"),
        (january(21), None, None, "USA"),
    ]


def test_added_row_overrides_old_row_on_all_dates_when_added_dates_contain_old_dates(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/5/2024,1/25/2024,BLA,USA\n") == [
        (january(5), january(9), None, "USA"),
        (january(10), january(20), "FRA", "USA"),
        (january(21), january(25), None, "USA"),
    ]


def test_added_row_overrides_first_part_of_old_row_when_it_has_only_end_date_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + ",1/15/2024,BLA,USA\n") == [
        (None, january(9), None, "USA"),
        (january(10), january(15), "FRA", "USA"),
    ]


def test_added_row_overrides_last_part_of_old_row_when_it_has_only_begin_date_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/15/2024,,BLA,USA\n") == [
        (january(15), january(20), "FRA", "USA"),
        (january(21), None, None, "USA"),
    ]


def test_added_row_overrides_first_part_of_old_row_when_it_begins_before_and_ends_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/5/2024,1/15/2024,BLA,USA\n") == [
        (january(5), january(9), None, "USA"),
        (january(10), january(15), "FRA", "USA"),
    ]


def test_added_row_overrides_last_part_of_old_row_when_it_begins_in_the_middle_and_ends_after(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/15/2024,1/25/2024,BLA,USA\n") == [
        (january(15), january(20), "FRA", "USA"),
        (january(21), january(25), None, "USA"),
    ]


def test_added_row_overrides_middle_part_of_old_row_when_it_begins_and_ends_in_the_middle(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/13/2024,1/17/2024,BLA,USA\n") == [
        (january(13), january(17), "FRA", "USA"),
    ]


def test_added_row_overrides_last_day_of_old_row_when_it_begins_on_the_day_old_row_ends(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/20/2024,1/30/2024,BLA,USA\n") == [
        (january(20), january(20), "FRA", "USA"),
        (january(21), january(30), None, "USA"),
    ]


def test_added_row_overrides_first_day_of_old_row_when_it_ends_on_the_day_old_row_begins(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/1/2024,1/10/2024,BLA,USA\n") == [
        (january(1), january(9), None, "USA"),
        (january(10), january(10), "FRA", "USA"),
    ]


def test_added_row_overrides_nothing_when_it_begins_on_the_day_after_old_row_ends(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/21/2024,1/30/2024,BLA,USA\n") == [
        (january(21), january(30), None, "USA"),
    ]


def test_no_diff_is_reported_when_added_row_overrides_middle_part_with_same_value(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, OLD_ROW + "1/13/2024,1/17/2024,BLA,FRA\n") == []


def test_old_row_wins_on_its_dates_when_wider_row_is_added_before_it(make_patch):
    assert effect_diffs(make_patch, OLD_ROW, "1/5/2024,1/25/2024,BLA,USA\n" + OLD_ROW) == [
        (january(5), january(9), None, "USA"),
        (january(21), january(25), None, "USA"),
    ]


def test_last_added_row_wins_when_two_added_rows_override_the_same_dates(make_patch):
    new_rows = OLD_ROW + "1/12/2024,1/18/2024,BLA,USA\n" + "1/14/2024,1/16/2024,BLA,GER\n"
    assert effect_diffs(make_patch, OLD_ROW, new_rows) == [
        (january(12), january(13), "FRA", "USA"),
        (january(14), january(16), "FRA", "GER"),
        (january(17), january(18), "FRA", "USA"),
    ]


# ---- one row written as two, and the edges of months and years


def test_no_diff_is_reported_when_old_row_is_split_into_two_adjacent_rows(make_patch):
    old_rows = "1/10/2024,1/30/2024,BLA,FRA\n"
    new_rows = "1/10/2024,1/20/2024,BLA,FRA\n" + "1/21/2024,1/30/2024,BLA,FRA\n"
    assert effect_diffs(make_patch, old_rows, new_rows) == []


def test_missing_day_is_reported_when_old_row_is_split_into_two_rows_with_a_gap(make_patch):
    old_rows = "1/10/2024,1/30/2024,BLA,FRA\n"
    new_rows = "1/10/2024,1/20/2024,BLA,FRA\n" + "1/22/2024,1/30/2024,BLA,FRA\n"
    assert effect_diffs(make_patch, old_rows, new_rows) == [(january(21), january(21), "FRA", None)]


def test_rows_share_no_day_when_old_row_ends_on_february_28_and_new_row_begins_on_leap_day(make_patch):
    old_rows = "2/1/2024,2/28/2024,BLA,FRA\n"
    new_rows = "2/29/2024,3/31/2024,BLA,USA\n"
    assert effect_diffs(make_patch, old_rows, new_rows) == [
        (date(2024, 2, 1), date(2024, 2, 28), "FRA", None),
        (date(2024, 2, 29), date(2024, 3, 31), None, "USA"),
    ]


def test_no_diff_is_reported_when_row_is_split_between_december_31_and_january_1(make_patch):
    old_rows = "12/1/2023,1/31/2024,BLA,FRA\n"
    new_rows = "12/1/2023,12/31/2023,BLA,FRA\n" + "20240101,20240131,BLA,FRA\n"
    assert effect_diffs(make_patch, old_rows, new_rows) == []
