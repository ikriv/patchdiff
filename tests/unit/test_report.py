"""The report text. The date logic is tested on the diff data, in test_date_overrides.py."""

from typing import Callable

from patchdiff.diff import diff_patches
from patchdiff.model.diff_model import PatchDiff
from patchdiff.model.patch_model import Patch
from patchdiff.report import (
    quote,
    render_diff,
    render_differences,
    render_title,
    render_warnings,
)

NO_DIFFERENCES = "No differences: the two patches do the same thing.\n"


def diff_of(make_patch: Callable[..., Patch], old_text: str, new_text: str) -> PatchDiff:
    return diff_patches(make_patch(old_text, name="old.csv"), make_patch(new_text, name="new.csv"))


def report(make_patch: Callable[..., Patch], old_text: str, new_text: str) -> str:
    return render_diff(diff_of(make_patch, old_text, new_text))


def test_quote_puts_value_on_one_line_when_value_has_line_breaks():
    assert quote("USA") == "'USA'"
    assert quote("") == "''"
    assert quote("Consumer Discretionary, etc.") == "'Consumer Discretionary, etc.'"
    assert quote("first line\nsecond line\r\nthird line") == "'first line second line third line'"
    assert quote("old Mac\rline break") == "'old Mac line break'"


def test_report_says_no_differences_when_patches_are_identical(make_patch):
    text = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """
    assert report(make_patch, text, text) == (
        "Old: old.csv\n"
        "New: new.csv\n"
        "\n"
        "No differences: the two patches do the same thing.\n"
    )


def test_report_says_no_differences_when_files_differ_and_patches_do_the_same_thing(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,FRA
        ,,JBL,USA
        ,,IGN,
    """
    new = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """
    # Row 2 of the old patch is redundant, row 4 has no values
    assert render_differences(diff_of(make_patch, old, new)) == NO_DIFFERENCES


def test_report_prints_columns_then_effect_diffs_then_warnings_when_patches_differ_in_columns_and_effect(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country,Foo,Bar,Empty
        ,,BLA,FRA,1,x,
        ,,IGN,,2,,
        20240301,20240201,JBL,USA,,,
    """
    new = """
        BeginDate,EndDate,Issuer,Country,Baz
        ,1/9/2024,BLA,USA,7
        1/10/2024,1/20/2024,BLA,USA,
    """
    assert report(make_patch, old, new) == (
        "Old: old.csv\n"
        "New: new.csv\n"
        "\n"
        "Removed column Bar\n"
        "Removed column Empty\n"
        "Removed column Foo\n"
        "Added column Baz\n"
        "\n"
        "Modified Issuer 'BLA':\n"
        "    Changed Country from 'FRA' to 'USA' for dates on or before 2024-01-20\n"
        "    Removed Country 'FRA' for dates on or after 2024-01-21\n"
        "    Removed Foo '1'\n"
        "    Removed Bar 'x'\n"
        "    Added Baz '7' for dates on or before 2024-01-09\n"
        "No longer patching Issuer 'IGN': Removed Foo '2'\n"
        "\n"
        "WARNINGS\n"
        "\n"
        "Old Patch:\n"
        "    Row 4: BeginDate=2024-03-01 is after EndDate=2024-02-01, the row does nothing\n"
        "        row 4: Issuer='JBL', BeginDate=2024-03-01, EndDate=2024-02-01, Country='USA'\n"
        "    Column Empty has no values and therefore does nothing\n"
    )


def test_report_prints_each_warning_with_its_rows_when_new_patch_has_every_kind_of_warning(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country,Sector
        ,,AAA,USA,Banks
    """
    new = """
        BeginDate,EndDate,Issuer,Country,Sector,Dead
        ,,AAA,USA,Banks,
        ,,AAA,FRA,,
        1/10/2024,1/20/2024,AAA,GER,Insurance,
        ,,,USA,,x
        ,,BBB,,,
        ,,CCC,USA,,
        ,,CCC,FRA,,
        ,,CCC,GER,,
        20240301,20240201,DDD,USA,,y
    """
    row_8 = "        row 8: Issuer='CCC', Country='FRA'\n"
    row_9 = "        row 9: Issuer='CCC', Country='GER'\n"
    assert render_warnings(diff_of(make_patch, old, new)) == (
        "WARNINGS\n"
        "\n"
        "New Patch:\n"
        "    Row 5: Issuer is blank, the row does nothing\n"
        "        row 5: Issuer='', Country='USA', Dead='x'\n"
        "    Row 6: no values, the row does nothing\n"
        "        row 6: Issuer='BBB' (all empty)\n"
        "    Row 7: redundant, rows 8 and 9 overwrite all its values\n"
        "        row 7: Issuer='CCC', Country='USA'\n"
        + row_8
        + row_9
        + "    Row 8: redundant, row 9 overwrites all its values\n"
        + row_8
        + row_9
        + "    Row 10: BeginDate=2024-03-01 is after EndDate=2024-02-01, the row does nothing\n"
        "        row 10: Issuer='DDD', BeginDate=2024-03-01, EndDate=2024-02-01, Country='USA', Dead='y'\n"
    )


def test_report_prints_one_line_per_column_when_column_is_in_one_patch_only(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country
        ,,AAA,USA
    """
    new = """
        BeginDate,EndDate,Issuer,Country,Mixed,Dead,OneDead,Empty
        ,,AAA,USA,1,,,
        ,,AAA,,2,,,
        ,,BBB,,3,,,
        ,,,,4,x,y,
        20240301,20240201,CCC,,5,z,,
    """
    # Mixed has 5 values. Row 3 overrides row 2, row 5 has no key, row 6 has reversed dates.
    assert render_differences(diff_of(make_patch, old, new)) == (
        "Added column Dead\n"
        "Added column Empty\n"
        "Added column Mixed\n"
        "Added column OneDead\n"
        "\n"
        "Modified Issuer 'AAA': Added Mixed '2'\n"
        "Now patching Issuer 'BBB': Added Mixed '3'\n"
    )


def test_report_prints_values_in_quotes_as_they_are_when_they_have_commas_or_punctuation(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Sector
        ,,A_B_C,"Banks, Insurance"
    """
    new = """
        BeginDate,EndDate,Issuer,Sector
        ,,A_B_C,x*y`z
    """
    assert render_differences(diff_of(make_patch, old, new)) == (
        "Modified Issuer 'A_B_C': Changed Sector from 'Banks, Insurance' to 'x*y`z'\n"
    )


def test_title_names_both_files_when_report_is_rendered(make_patch):
    text = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """
    assert render_title(diff_of(make_patch, text, text)) == (
        "Old: old.csv\n"
        "New: new.csv\n"
    )


def test_report_says_dates_in_words_as_yyyy_mm_dd_when_changes_have_open_and_closed_date_ranges(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country
        ,,ALL,USA
        ,,BEGIN,USA
        ,,END,USA
        ,,BOTH,USA
        ,,DAY,USA
    """
    new = """
        BeginDate,EndDate,Issuer,Country
        ,,ALL,FRA
        ,,BEGIN,USA
        2/1/2024,,BEGIN,FRA
        ,,END,USA
        ,1/31/2024,END,FRA
        ,,BOTH,USA
        1/10/2024,1/20/2024,BOTH,FRA
        ,,DAY,USA
        1/15/2024,1/15/2024,DAY,FRA
    """
    assert render_differences(diff_of(make_patch, old, new)) == (
        "Modified Issuer 'ALL': Changed Country from 'USA' to 'FRA'\n"
        "Modified Issuer 'BEGIN': Changed Country from 'USA' to 'FRA' for dates on or after 2024-02-01\n"
        "Modified Issuer 'BOTH': Changed Country from 'USA' to 'FRA' for dates between 2024-01-10 and 2024-01-20\n"
        "Modified Issuer 'DAY': Changed Country from 'USA' to 'FRA' for 2024-01-15\n"
        "Modified Issuer 'END': Changed Country from 'USA' to 'FRA' for dates on or before 2024-01-31\n"
    )


def test_report_says_added_removed_or_changed_when_value_is_set_by_new_patch_only_old_patch_only_or_both(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Banks
        ,,AMT,Bob,Housing
        ,,TSLA,,Cars
    """
    new = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Mike,Banks
        ,,AMT,,Housing
        ,,TSLA,Emily,Cars
    """
    assert render_differences(diff_of(make_patch, old, new)) == (
        "Modified Issuer 'AMT': Removed Analyst 'Bob'\n"
        "Modified Issuer 'MSFT': Changed Analyst from 'Bob' to 'Mike'\n"
        "Modified Issuer 'TSLA': Added Analyst 'Emily'\n"
    )


def test_key_takes_one_line_when_it_has_one_change_and_one_line_per_change_when_it_has_more(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Banks
    """
    new = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Mike,Banks
        ,,IRM,Emily,Real Estate
        20250112,20250112,IRM,,Housing
    """
    # The changes of one key are sorted by column, in the column order of the old patch, then by date
    assert render_differences(diff_of(make_patch, old, new)) == (
        "Now patching Issuer 'IRM':\n"
        "    Added Analyst 'Emily'\n"
        "    Added Sector 'Real Estate' for dates on or before 2025-01-11\n"
        "    Added Sector 'Housing' for 2025-01-12\n"
        "    Added Sector 'Real Estate' for dates on or after 2025-01-13\n"
        "Modified Issuer 'MSFT': Changed Analyst from 'Bob' to 'Mike'\n"
    )


def test_report_says_now_patching_or_no_longer_patching_when_only_one_patch_sets_values_for_key(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Banks
        1/1/2024,1/31/2024,AMT,Bob,Real Estate
    """
    new = """
        BeginDate,EndDate,Issuer,Analyst,Sector
        ,,MSFT,Bob,Banks
        ,,TSLA,Emily,
    """
    assert render_differences(diff_of(make_patch, old, new)) == (
        "No longer patching Issuer 'AMT':\n"
        "    Removed Analyst 'Bob' for dates between 2024-01-01 and 2024-01-31\n"
        "    Removed Sector 'Real Estate' for dates between 2024-01-01 and 2024-01-31\n"
        "Now patching Issuer 'TSLA': Added Analyst 'Emily'\n"
    )


def test_report_is_its_parts_with_a_blank_line_between_when_put_together(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
    """
    new = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,FRA
        ,,,GER
    """
    diff = diff_of(make_patch, old, new)
    title, differences, warnings = render_title(diff), render_differences(diff), render_warnings(diff)
    assert render_diff(diff) == "\n".join([title, differences, warnings])
    assert render_diff(diff, with_warnings=False) == "\n".join([title, differences])
    assert all(part.endswith("\n") and not part.endswith("\n\n") for part in (title, differences, warnings))


def test_report_has_a_subsection_for_each_patch_that_has_warnings_when_both_patches_have_them(make_patch):
    old = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,IGN,
    """
    new = """
        BeginDate,EndDate,Issuer,Country
        ,,JBL,USA
        ,,,GER
    """
    assert report(make_patch, old, new) == (
        "Old: old.csv\n"
        "New: new.csv\n"
        "\n"
        "No differences: the two patches do the same thing.\n"
        "\n"
        "WARNINGS\n"
        "\n"
        "Old Patch:\n"
        "    Row 3: no values, the row does nothing\n"
        "        row 3: Issuer='IGN' (all empty)\n"
        "\n"
        "New Patch:\n"
        "    Row 3: Issuer is blank, the row does nothing\n"
        "        row 3: Issuer='', Country='GER'\n"
    )
