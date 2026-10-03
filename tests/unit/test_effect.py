from datetime import date

from patchdiff.effect import build_effect, ranges_overlap, split_into_non_overlapping_ranges
from patchdiff.model.effect_model import ValueUpdate
from patchdiff.model.patch_date import INFINITE_FUTURE, INFINITE_PAST, PatchDate
from patchdiff.model.patch_model import DateRange, Patch


def updates(patch: Patch, key: str, column: str) -> list[tuple[date | None, date | None, str]]:
    """Timeline as readable tuples: (first day, last day, value). None means no limit."""
    return [
        (update.dates.first_day, update.dates.last_day, update.value)
        for update in build_effect(patch).get_timeline(key, column)
    ]


def test_later_row_wins_when_two_rows_set_same_column_for_all_dates(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,PIPR,FRA
        ,,PIPR,USA
    """)
    assert updates(patch, "PIPR", "Country") == [(None, None, "USA")]


def test_earlier_row_keeps_its_other_columns_when_later_row_overrides_one_column(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country,Price,Currency
        ,,BLA,FRA,14,
        ,,BLA,USA,,USD
    """)
    assert updates(patch, "BLA", "Country") == [(None, None, "USA")]
    assert updates(patch, "BLA", "Price") == [(None, None, "14")]
    assert updates(patch, "BLA", "Currency") == [(None, None, "USD")]


def test_timeline_splits_in_three_when_later_row_covers_dates_in_the_middle(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
        1/10/2024,1/20/2024,BLA,USA
    """)
    assert updates(patch, "BLA", "Country") == [
        (None, date(2024, 1, 9), "FRA"),
        (date(2024, 1, 10), date(2024, 1, 20), "USA"),
        (date(2024, 1, 21), None, "FRA"),
    ]


def test_later_row_wins_on_shared_day_when_it_begins_on_end_date_of_earlier_row(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/10/2024,BLA,FRA
        1/10/2024,,BLA,USA
    """)
    assert updates(patch, "BLA", "Country") == [
        (None, date(2024, 1, 9), "FRA"),
        (date(2024, 1, 10), None, "USA"),
    ]


def test_timeline_has_gap_when_no_row_covers_some_dates(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/10/2024,BLA,FRA
        1/21/2024,,BLA,USA
    """)
    assert updates(patch, "BLA", "Country") == [
        (None, date(2024, 1, 10), "FRA"),
        (date(2024, 1, 21), None, "USA"),
    ]


def test_earlier_row_leaves_no_trace_when_later_row_covers_all_its_dates(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        1/10/2024,1/20/2024,BLA,USA
        ,,BLA,FRA
    """)
    # The later row is cut at the dates of the earlier one, then joined back
    assert updates(patch, "BLA", "Country") == [(None, None, "FRA")]


def test_updates_are_joined_when_two_rows_set_same_value_on_adjacent_dates(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/9/2024,BLA,USA
        1/10/2024,1/20/2024,BLA,USA
        1/21/2024,,BLA,FRA
    """)
    assert updates(patch, "BLA", "Country") == [
        (None, date(2024, 1, 20), "USA"),
        (date(2024, 1, 21), None, "FRA"),
    ]


def test_updates_are_not_joined_when_two_rows_set_same_value_with_a_gap_between_them(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/9/2024,BLA,USA
        1/11/2024,,BLA,USA
    """)
    assert updates(patch, "BLA", "Country") == [
        (None, date(2024, 1, 9), "USA"),
        (date(2024, 1, 11), None, "USA"),
    ]


def test_effect_knows_lines_of_rows_whose_values_cause_changes_when_some_values_are_overwritten(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country,Sector,Empty
        ,,BLA,FRA,Banks,
        ,,BLA,USA,,
        1/10/2024,1/20/2024,BLA,GER,,
        ,,,MEX,,
    """)
    # Row 2 keeps its Sector. Row 4 overwrites only part of row 3. Row 5 has no key, so it does nothing.
    assert build_effect(patch).lines_of_effective_rows == frozenset({2, 3, 4})


def test_earlier_value_stays_when_later_row_has_blank_in_that_column(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country,Sector
        ,,BLA,FRA,Banks
        ,,BLA,,Insurance
    """)
    assert updates(patch, "BLA", "Country") == [(None, None, "FRA")]


def test_effect_skips_rows_when_key_is_blank_or_dates_are_reversed(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
        20240301,20240201,BLA,USA
        ,,,GER
    """)
    assert build_effect(patch).timelines_per_key_and_column.keys() == {"BLA"}
    assert updates(patch, "BLA", "Country") == [(None, None, "FRA")]


def test_effect_is_empty_when_key_has_only_blank_values(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,IGN,
    """)
    assert build_effect(patch).timelines_per_key_and_column == {}


def test_timelines_stay_separate_when_rows_have_different_keys(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,AAA,FRA
        ,,BBB,USA
    """)
    assert updates(patch, "AAA", "Country") == [(None, None, "FRA")]
    assert updates(patch, "BBB", "Country") == [(None, None, "USA")]
    assert updates(patch, "CCC", "Country") == []


def test_split_cuts_at_every_begin_and_end_when_ranges_overlap_or_leave_gaps():
    assert split_into_non_overlapping_ranges([]) == []
    assert split_into_non_overlapping_ranges([DateRange()]) == [DateRange()]
    # An overlap in the middle gives three stretches, a gap between ranges is a stretch too
    assert split_into_non_overlapping_ranges([
        DateRange(),
        DateRange.from_dates(date(2024, 1, 10), date(2024, 1, 20)),
    ]) == [
        DateRange.from_dates(None, date(2024, 1, 9)),
        DateRange.from_dates(date(2024, 1, 10), date(2024, 1, 20)),
        DateRange.from_dates(date(2024, 1, 21), None),
    ]
    assert split_into_non_overlapping_ranges([
        DateRange.from_dates(None, date(2024, 1, 10)),
        DateRange.from_dates(date(2024, 1, 21), None),
    ]) == [
        DateRange.from_dates(None, date(2024, 1, 10)),
        DateRange.from_dates(date(2024, 1, 11), date(2024, 1, 20)),
        DateRange.from_dates(date(2024, 1, 21), None),
    ]


def test_value_update_ends_on_end_date_when_row_has_end_date(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/10/2024,BLA,FRA
        1/21/2024,,BLA,USA
    """)
    assert build_effect(patch).get_timeline("BLA", "Country") == (
        ValueUpdate(DateRange(INFINITE_PAST, PatchDate(date(2024, 1, 10))), "FRA"),
        ValueUpdate(DateRange(PatchDate(date(2024, 1, 21)), INFINITE_FUTURE), "USA"),
    )


def test_value_update_has_no_limits_when_row_uses_first_and_last_possible_dates(make_patch):
    patch = make_patch("""
        BeginDate,EndDate,Issuer,Country
        01/01/0001,12/31/9999,BLA,FRA
    """)
    assert build_effect(patch).get_timeline("BLA", "Country") == (ValueUpdate(DateRange(), "FRA"),)
    assert build_effect(patch).get_timeline("NONE", "Country") == ()


def test_ranges_overlap_when_they_share_at_least_one_day():
    january = DateRange.from_dates(date(2024, 1, 1), date(2024, 1, 31))
    from_mid_january = DateRange.from_dates(date(2024, 1, 15), None)
    february = DateRange.from_dates(date(2024, 2, 1), date(2024, 2, 29))
    assert ranges_overlap(january, DateRange())
    assert ranges_overlap(january, from_mid_january)
    assert ranges_overlap(from_mid_january, january)
    assert not ranges_overlap(january, february)
    assert not ranges_overlap(february, january)
    # One shared day is enough
    assert ranges_overlap(january, DateRange.from_dates(date(2024, 1, 31), None))
    assert ranges_overlap(DateRange.from_dates(date(2024, 1, 31), None), january)
