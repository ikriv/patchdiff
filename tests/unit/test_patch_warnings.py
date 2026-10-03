from typing import Callable

from patchdiff.effect import build_effect
from patchdiff.model.patch_model import DateRange, NoOpRowReason, Patch, PatchRow
from patchdiff.model.warning_model import EmptyColumnWarning, NoOpRowWarning, PatchWarning, RedundantRowWarning
from patchdiff.patch_warnings import find_warnings

ALL_DATES = DateRange()


def find(make_patch: Callable[..., Patch], text: str) -> list[PatchWarning]:
    patch = make_patch(text)
    return find_warnings(patch, build_effect(patch))


def summary(warning: PatchWarning) -> tuple[object, ...]:
    """A warning as a short tuple, with line numbers in place of whole rows."""
    match warning:
        case NoOpRowWarning():
            return "no-op row", warning.row.line, warning.row.noop_reason
        case RedundantRowWarning():
            return "redundant row", warning.row.line, tuple(row.line for row in warning.overridden_by)
        case EmptyColumnWarning():
            return "empty column", warning.column


def summaries(make_patch: Callable[..., Patch], text: str) -> list[tuple[object, ...]]:
    return [summary(warning) for warning in find(make_patch, text)]


def test_no_warnings_are_found_when_patch_is_clean(make_patch):
    assert find(make_patch, """
        BeginDate,EndDate,Issuer,Country,Sector
        ,,JBL,USA,Computers
        ,1/9/2024,FR,USA,
        1/10/2024,,FR,FRA,Banks
    """) == []


def test_noop_row_warning_is_raised_when_row_has_blank_key_reversed_dates_or_no_values(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,,FRA
        20240301,20240201,JBL,FRA
        ,,IGN,
    """) == [
        ("no-op row", 3, NoOpRowReason.BLANK_KEY),
        ("no-op row", 4, NoOpRowReason.REVERSED_DATES),
        ("no-op row", 5, NoOpRowReason.NO_VALUES),
    ]


def test_row_gets_one_warning_when_it_has_several_problems(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        20240301,20240201,,
    """) == [("no-op row", 3, NoOpRowReason.BLANK_KEY)]


def test_redundant_row_warning_is_raised_when_later_row_overwrites_all_values(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,PIPR,FRA
        ,,PIPR,USA
    """) == [("redundant row", 2, (3,))]


def test_redundant_row_warning_is_raised_when_several_rows_override_row_piece_by_piece(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country,Sector
        ,,BLA,FRA,Banks
        ,1/9/2024,BLA,USA,
        1/10/2024,,BLA,GER,
        ,,BLA,,Insurance
    """) == [("redundant row", 2, (3, 4, 5))]


def test_each_row_gets_redundant_warning_when_rows_override_each_other_in_a_chain(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,CCC,USA
        ,,CCC,FRA
        ,,CCC,GER
    """) == [
        ("redundant row", 2, (3, 4)),
        ("redundant row", 3, (4,)),
    ]


def test_redundant_row_warning_names_only_later_rows_of_same_key_that_set_same_column_on_shared_dates(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country,Sector
        ,,OTHER,GER,
        ,1/9/2024,BLA,FRA,
        1/10/2024,,BLA,USA,
        ,,OTHER,GER,
        ,,BLA,,Banks
        ,,BLA,GER,
    """) == [
        # Row 5 has another key
        ("redundant row", 2, (5,)),
        # Row 4 covers other dates, row 5 has another key, row 6 sets another column
        ("redundant row", 3, (7,)),
        # Row 3 comes earlier, rows 5 and 6 as above
        ("redundant row", 4, (7,)),
    ]


def test_no_warning_is_raised_when_later_row_overwrites_a_value_on_some_of_the_dates(make_patch):
    assert find(make_patch, """
        BeginDate,EndDate,Issuer,Country,Conviction
        ,,FR,USA,
        20240201,,FR,FRA,Low
    """) == []


def test_no_warning_is_raised_when_later_row_overwrites_one_value_and_row_keeps_another(make_patch):
    assert find(make_patch, """
        BeginDate,EndDate,Issuer,Country,Conviction,Sector
        ,,PIPR,FRA,,Consumer Discretionary
        ,,PIPR,USA,High,
    """) == []


def test_only_noop_row_warning_is_raised_when_row_that_does_nothing_sets_same_column_as_another_row(make_patch):
    # Row 3 does nothing, so it does not make row 2 redundant, and it is not called redundant itself
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        20240301,20240201,JBL,FRA
    """) == [("no-op row", 3, NoOpRowReason.REVERSED_DATES)]


def test_empty_column_warning_is_raised_when_column_has_no_values(make_patch):
    # Dead has a value, in a row that does nothing. That row has a warning, the column does not get another one.
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country,Empty,Dead
        ,,JBL,USA,,
        ,,,,,x
    """) == [
        ("no-op row", 3, NoOpRowReason.BLANK_KEY),
        ("empty column", "Empty"),
    ]


def test_row_warnings_are_sorted_by_row_and_column_warnings_come_last_when_kinds_are_mixed(make_patch):
    assert summaries(make_patch, """
        BeginDate,EndDate,Issuer,Country,Empty
        ,,,USA,
        ,,AAA,USA,
        ,,BBB,,
        ,,AAA,FRA,
    """) == [
        ("no-op row", 2, NoOpRowReason.BLANK_KEY),
        ("redundant row", 3, (5,)),
        ("no-op row", 4, NoOpRowReason.NO_VALUES),
        ("empty column", "Empty"),
    ]


def test_warnings_hold_whole_rows_when_they_are_about_rows(make_patch):
    row_2 = PatchRow(2, "DDD", ALL_DATES, {"Country": "USA"})
    row_3 = PatchRow(3, "DDD", ALL_DATES, {"Country": "FRA"})
    row_4 = PatchRow(4, "", ALL_DATES, {"Country": "GER"})
    assert find(make_patch, """
        BeginDate,EndDate,Issuer,Country
        ,,DDD,USA
        ,,DDD,FRA
        ,,,GER
    """) == [
        RedundantRowWarning(row_2, overridden_by=(row_3,)),
        NoOpRowWarning(row_4),
    ]
