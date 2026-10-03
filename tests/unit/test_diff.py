from datetime import date

import pytest

from patchdiff.diff import diff_patches
from patchdiff.model.diff_model import EffectDiff, PatchDiff
from patchdiff.model.patch_model import DateRange, PatchError

ALL_DATES = DateRange()


def has_no_changes(diff: PatchDiff) -> bool:
    # Warnings are about each patch on its own, they are not changes
    return not (diff.columns_only_in_old or diff.columns_only_in_new or diff.effect_diffs)


# ---- columns


def test_diff_raises_error_when_key_columns_differ(make_patch):
    old = make_patch("BeginDate,EndDate,Issuer,Country\n")
    new = make_patch("BeginDate,EndDate,Ticker,Country\n")
    with pytest.raises(PatchError, match="key columns differ"):
        diff_patches(old, new)


def test_diff_reports_nothing_when_only_column_order_differs(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Sector
        ,,JBL,USA,Computers
    """)
    new = make_patch("""
        Issuer,Sector,EndDate,Country,BeginDate
        JBL,Computers,,USA,
    """)
    assert has_no_changes(diff_patches(old, new))


def test_diff_reports_columns_that_are_in_one_patch_only_sorted_by_name(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Foo,Empty
        ,,JBL,USA,1,
        ,,FR,USA,2,
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Analyst
        ,,JBL,USA,Bob
        ,,FR,USA,
    """)
    diff = diff_patches(old, new)
    assert diff.columns_only_in_old == ("Empty", "Foo")
    assert diff.columns_only_in_new == ("Analyst",)


def test_effect_diff_has_no_value_on_one_side_when_column_is_in_one_patch_only(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Foo,Empty
        ,,JBL,USA,1,
        ,,FR,USA,2,
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Analyst
        ,,JBL,FRA,Bob
        ,,FR,USA,
        ,,IBM,,Emily
    """)
    # A column that is in one patch only is compared like any other column.
    # Columns of the old patch come first, then the columns that only the new patch has.
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("FR", "Foo", ALL_DATES, "2", None),
        EffectDiff("IBM", "Analyst", ALL_DATES, None, "Emily"),
        EffectDiff("JBL", "Country", ALL_DATES, "USA", "FRA"),
        EffectDiff("JBL", "Foo", ALL_DATES, "1", None),
        EffectDiff("JBL", "Analyst", ALL_DATES, None, "Bob"),
    ]


def test_diff_names_keys_that_only_one_patch_sets_values_for_when_key_is_added_or_removed(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,GONE,USA
        ,,EMPTY,
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,FRA
        20240101,,NEW,USA
        ,,,GER
    """)
    diff = diff_patches(old, new)
    # A key whose rows set nothing is in neither set: EMPTY has no values, and the last row has no key
    assert diff.keys_only_in_old == {"GONE"}
    assert diff.keys_only_in_new == {"NEW"}


# ---- effect


def test_diff_reports_nothing_when_patches_are_identical(make_patch):
    text = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        20240201,,FR,FRA
    """
    assert has_no_changes(diff_patches(make_patch(text), make_patch(text)))


def test_diff_reports_nothing_when_only_date_format_differs(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        20240201,20240229,FR,FRA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        2/1/2024,02/29/2024,FR,FRA
    """)
    assert has_no_changes(diff_patches(old, new))


def test_diff_reports_nothing_when_rows_of_different_keys_change_order(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,FR,FRA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,FR,FRA
        ,,JBL,USA
    """)
    assert has_no_changes(diff_patches(old, new))


def test_effect_diff_lists_only_the_changed_column_when_one_value_changes(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Information Technology
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Mike,Information Technology
    """)
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("MSFT", "Analyst", ALL_DATES, "Bob", "Mike"),
    ]


def test_effect_diff_has_no_old_value_when_value_is_added_to_existing_key(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,TSLA,,Consumer Discretionary
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,TSLA,Bob,Consumer Discretionary
    """)
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("TSLA", "Analyst", ALL_DATES, None, "Bob"),
    ]


def test_effect_diff_has_no_value_on_one_side_when_key_is_in_one_patch_only(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Information Technology
        1/1/2024,1/31/2024,AMT,Bob,Real Estate
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Information Technology
        ,,IRM,Emily,Real Estate
    """)
    diff = diff_patches(old, new)
    january = DateRange.from_dates(date(2024, 1, 1), date(2024, 1, 31))
    assert list(diff.effect_diffs) == [
        EffectDiff("AMT", "Analyst", january, "Bob", None),
        EffectDiff("AMT", "Sector", january, "Real Estate", None),
        EffectDiff("IRM", "Analyst", ALL_DATES, None, "Emily"),
        EffectDiff("IRM", "Sector", ALL_DATES, None, "Real Estate"),
    ]


def test_effect_diff_covers_only_overridden_dates_when_new_row_overrides_part_of_date_range(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
        1/10/2024,1/20/2024,BLA,USA
    """)
    dates = DateRange.from_dates(date(2024, 1, 10), date(2024, 1, 20))
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("BLA", "Country", dates, "FRA", "USA"),
    ]


def test_effect_diff_has_one_date_range_when_two_rows_set_the_same_value_on_adjacent_dates(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,1/9/2024,BLA,USA
        1/10/2024,,BLA,USA
    """)
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("BLA", "Country", ALL_DATES, "FRA", "USA"),
    ]


def test_each_column_gets_its_own_date_range_when_columns_differ_on_different_dates(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction
        ,,FR,USA,Low
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction
        ,,FR,USA,High
        20240201,,FR,FRA,
    """)
    assert list(diff_patches(old, new).effect_diffs) == [
        # Country comes first in the file. Conviction differs on all dates, Country from February on.
        EffectDiff("FR", "Country", DateRange.from_dates(date(2024, 2, 1), None), "USA", "FRA"),
        EffectDiff("FR", "Conviction", ALL_DATES, "Low", "High"),
    ]


def test_each_column_gets_its_own_effect_diff_when_columns_differ_on_the_same_dates(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction,Sector
        ,,FR,USA,Low,Banks
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction,Sector
        ,,FR,USA,Low,Banks
        1/10/2024,1/20/2024,FR,FRA,High,
    """)
    dates = DateRange.from_dates(date(2024, 1, 10), date(2024, 1, 20))
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("FR", "Country", dates, "USA", "FRA"),
        EffectDiff("FR", "Conviction", dates, "Low", "High"),
    ]


def test_effect_diffs_of_one_key_may_overlap_in_dates_when_each_column_changes_from_its_own_date(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction,Industry
        ,,BLA,USA,Low,Banks
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Conviction,Industry
        ,,BLA,USA,Low,Banks
        20240110,,BLA,FRA,,
        20240120,,BLA,,High,
        20240130,,BLA,,,Insurance
    """)
    # Three changes give three effect diffs with one column each. No column is repeated.
    assert list(diff_patches(old, new).effect_diffs) == [
        EffectDiff("BLA", "Country", DateRange.from_dates(date(2024, 1, 10), None), "USA", "FRA"),
        EffectDiff("BLA", "Conviction", DateRange.from_dates(date(2024, 1, 20), None), "Low", "High"),
        EffectDiff("BLA", "Industry", DateRange.from_dates(date(2024, 1, 30), None), "Banks", "Insurance"),
    ]


def test_effect_diffs_of_one_key_are_sorted_by_column_order_of_old_patch_then_by_date(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Conviction,Country
        ,,BLA,Low,USA
    """)
    new = make_patch("""
        Issuer,BeginDate,EndDate,Country,Conviction,Analyst
        BLA,,,USA,Low,
        BLA,20240110,,FRA,,Bob
        BLA,20240101,20240105,,High,
        BLA,20240120,20240125,,High,
    """)
    assert [(effect_diff.column, effect_diff.dates.first_day) for effect_diff in diff_patches(old, new).effect_diffs] == [
        # Conviction before Country, as in the old patch. Analyst last, only the new patch has it.
        ("Conviction", date(2024, 1, 1)),
        ("Conviction", date(2024, 1, 20)),
        ("Country", date(2024, 1, 10)),
        ("Analyst", date(2024, 1, 10)),
    ]


def test_diffs_are_sorted_by_key_when_keys_are_in_random_order(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,ZZZ,USA
        ,,bbb,USA
        ,,AAA,USA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,ZZZ,FRA
        ,,bbb,FRA
        ,,AAA,FRA
    """)
    diff = diff_patches(old, new)
    assert [effect_diff.key for effect_diff in diff.effect_diffs] == ["AAA", "ZZZ", "bbb"]


# ---- same effect


def test_diff_reports_nothing_when_redundant_row_is_removed(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Price
        ,,BLA,FRA,12
        ,,BLA,USA,
        ,,JBL,USA,
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Price
        ,,JBL,USA,
        ,,BLA,USA,
        ,,BLA,,12
    """)
    assert has_no_changes(diff_patches(old, new))


def test_diff_reports_nothing_when_row_without_values_is_removed(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,IGN,
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """)
    assert has_no_changes(diff_patches(old, new))


def test_diff_reports_nothing_when_reordered_rows_of_one_key_set_different_columns(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country,Price
        ,,BLA,USA,
        ,,BLA,,12
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country,Price
        ,,BLA,,12
        ,,BLA,USA,
    """)
    assert has_no_changes(diff_patches(old, new))


def test_effect_diff_reports_other_value_when_reordered_rows_of_one_key_set_same_column(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,FRA
        ,,BLA,USA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,BLA,USA
        ,,BLA,FRA
    """)
    diff = diff_patches(old, new)
    assert list(diff.effect_diffs) == [
        EffectDiff("BLA", "Country", ALL_DATES, "USA", "FRA"),
    ]


# ---- rows that do nothing. The warnings themselves are tested in test_patch_warnings.py


def test_row_changes_no_effect_when_begin_date_is_after_end_date(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        20240301,20240201,JBL,FRA
    """)
    diff = diff_patches(old, new)
    assert list(diff.effect_diffs) == []


def test_diff_reports_change_when_only_the_case_of_a_value_differs(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,JBL,Bob
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Analyst
        ,,JBL,bob
    """)
    assert list(diff_patches(old, new).effect_diffs) == [EffectDiff("JBL", "Analyst", ALL_DATES, "Bob", "bob")]


def test_diff_reports_change_when_values_are_the_same_number_written_differently(make_patch):
    old = make_patch("""
        BeginDate,EndDate,Issuer,Price
        ,,JBL,1
    """)
    new = make_patch("""
        BeginDate,EndDate,Issuer,Price
        ,,JBL,1.0
    """)
    # Values are text. The tool does not know that 1 and 1.0 are the same number.
    assert list(diff_patches(old, new).effect_diffs) == [EffectDiff("JBL", "Price", ALL_DATES, "1", "1.0")]
