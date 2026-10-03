# patchdiff

Compares two patch files in CSV format and prints a human readable diff as plain text. The report shows how applying the new patch differs from applying the old patch.

## Run

The tool needs Python 3.11 or later. There are no packages to install.

```
python -m patchdiff samples/Patch3.csv samples/Patch4.csv
```

The first file is the old patch, the second is the new patch. The report is plain text.

After the differences, the report lists warnings: rows and columns that look like a mistake, for each patch on its own. To leave the warnings out, pass `--no-warnings`:

```
python -m patchdiff --no-warnings samples/Patch3.csv samples/Patch4.csv
```

The files are read as UTF-8, or in the local encoding of the machine if they are not valid UTF-8 (see "Text encoding" below). To name the encoding of both files yourself, pass `--encoding`:

```
python -m patchdiff old.csv new.csv --encoding cp1250
```

The exit code is 0 if the tool compared the two patches, and 2 if it could not: a file was not found, a file is not a valid patch, or the two patches have different key columns. The error message goes to stderr.

## What the report looks like

The report focuses on the differences between how the patches are applied, as opposed to the difference in the textual representation. Patches that have the same effect may be represented with radically different texts. So the tool works out, for each key and column, which value applies on which dates in each patch, and reports where the two patches differ. Added or removed columns get a line of their own, and rows that look like a mistake get a warning. How this is calculated, and what was tried and rejected, is described under "Implementation Details".

### The example from the requirements document

The task document gives two patches as an example. The old patch:

```
Issuer,BeginDate,EndDate,Analyst,Sector
MSFT,,,Bob,Information Technology
CAT,1/1/2024,,Emily,
TSLA,,,,Consumer Discretionary
AMT,1/1/2024,1/31/2024,Bob,Real Estate
```

The new patch:

```
Issuer,BeginDate,EndDate,Analyst,Sector
MSFT,,,Mike,Information Technology
CAT,1/1/2024,,Emily,
TSLA,,,Bob,Consumer Discretionary
AMT,1/1/2024,1/31/2024,Bob,Real Estate
IRM,,,Emily,Real Estate
```

Both files are in `tests/e2e/cases/success/task_document_example`. The tool prints:

```
Old: old.csv
New: new.csv

Now patching Issuer 'IRM':
    Added Analyst 'Emily'
    Added Sector 'Real Estate'
Modified Issuer 'MSFT': Changed Analyst from 'Bob' to 'Mike'
Modified Issuer 'TSLA': Added Analyst 'Bob'
```

The analyst of MSFT changes from Bob to Mike, TSLA gets an analyst, and IRM is a new key. CAT and AMT are the same in both patches, so they are not in the report.

### Extended example

The two patches below are made up to show every kind of line the report has. They are in `tests/e2e/cases/success/readme_example`. The old patch:

```
BeginDate,EndDate,Issuer,Country,Sector,Analyst
,,ACME,USA,Banks,Bob
,,BLA,FRA,,Emily
1/1/2024,1/31/2024,CORP,GER,Insurance,
,,GONE,MEX,,Ann
,,,USA,,
```

The new patch, with the Analyst column removed, a Conviction column added, a few dates, one issuer dropped, one added, and one row with the dates the wrong way round:

```
BeginDate,EndDate,Issuer,Country,Sector,Conviction
,,ACME,USA,Banks,High
,1/9/2024,ACME,FRA,,
1/20/2024,1/20/2024,ACME,CAN,,
1/10/2024,1/15/2024,ACME,,Insurance,
2/1/2024,,BLA,FRA,,
1/1/2024,1/31/2024,CORP,GER,Insurance,
2/1/2024,,CORP,,Banks,
3/1/2024,1/1/2024,GONE,MEX,,
,,NEWCO,USA,,Low
```

The tool output:

```
Old: old.csv
New: new.csv

Removed column Analyst
Added column Conviction

Modified Issuer 'ACME':
    Changed Country from 'USA' to 'FRA' for dates on or before 2024-01-09
    Changed Country from 'USA' to 'CAN' for 2024-01-20
    Changed Sector from 'Banks' to 'Insurance' for dates between 2024-01-10 and 2024-01-15
    Removed Analyst 'Bob'
    Added Conviction 'High'
Modified Issuer 'BLA':
    Removed Country 'FRA' for dates on or before 2024-01-31
    Removed Analyst 'Emily'
Modified Issuer 'CORP': Added Sector 'Banks' for dates on or after 2024-02-01
No longer patching Issuer 'GONE':
    Removed Country 'MEX'
    Removed Analyst 'Ann'
Now patching Issuer 'NEWCO':
    Added Country 'USA'
    Added Conviction 'Low'

WARNINGS

Old Patch:
    Row 6: Issuer is blank, the row does nothing
        row 6: Issuer='', Country='USA'

New Patch:
    Row 9: BeginDate=2024-03-01 is after EndDate=2024-01-01, the row does nothing
        row 9: Issuer='GONE', BeginDate=2024-03-01, EndDate=2024-01-01, Country='MEX'
```

A few notes on format:

* A date is shown only when it limits the date range.
* "for dates between X and Y" includes both X and Y. "for dates on or after X" and "for dates on or before Y" include X and Y as well.
* "for 2024-02-01" means exactly one day.

### The same effect, written differently

The two patches below are in `tests/e2e/cases/success/same_effect_written_differently`. The old patch:

```
BeginDate,EndDate,Issuer,Country,Sector
,,JBL,USA,Computers
1/10/2024,1/30/2024,BLA,FRA,
20240201,,FR,GER,Banks
```

The new patch has the columns in another order, the rows in another order, the dates in another format, and the BLA row split into two rows that follow each other:

```
Issuer,Sector,BeginDate,EndDate,Country
FR,Banks,2/1/2024,,GER
BLA,,1/10/2024,1/20/2024,FRA
BLA,,1/21/2024,1/30/2024,FRA
JBL,Computers,,,USA
```

None of that changes what the patch does, so the report is:

```
Old: old.csv
New: new.csv

No differences: the two patches do the same thing.
```

## Testing

```
pip install pytest
python -m pytest
```

The code is fully typed and passes mypy in strict mode:

```
pip install mypy
python -m mypy patchdiff --strict
```

See "Testing details" below for more information.

## Assumptions

1. Rows are applied top to bottom. A later row wins over an earlier row.
2. Dates are `MM/DD/YYYY`, `YYYYMMDD` or `YYYY-MM-DD`. `1/4/2025` is always January 4, whatever the locale of the machine. Dates have no time of day.
3. Date ranges include both ends.
4. Leading and trailing whitespace is ignored, in values and in column names. Case matters: `Bob` is not `bob`.
5. A blank value means "don't touch". A patch cannot set a value to blank.
6. A row with a blank key does nothing.
7. Values are compared as text. `1` and `1.0` are different.
8. A row where BeginDate is after EndDate covers no dates. Such a row does nothing and gets a warning.
9. Lines where every cell is blank have no effect.

## Text encoding

A file is read as UTF-8 first. If it is not valid UTF-8, it is read in the local encoding of the machine that runs the tool. 

`--encoding` overrides both. 

This fallback is the one thing that depends on the machine. It exists because Excel's plain "CSV (Comma delimited)" export writes the file in the code page of the machine, not in UTF-8.

## Errors

The tool returns with an error if the key columns are different between the two files.

It also fails if either file has any of the problems below. The error message names the file, and also the row when the problem is in one row: 

* The file cannot be read in any of the encodings above.
* The `BeginDate` or `EndDate` column is missing.
* There is no key column.
* A column name appears twice.
* A date cannot be read.
* A value sits in a column that has no name.

# Implementation Details

The long section below describes the internals: implementation details, alternatives considered, known issues, and tradeoffs. The intended audience is reviewers and developers, not necessarily the users.

## Code structure

```
patchdiff/
  model/
    patch_model.py   PatchText, Patch, PatchRow, DateRange, NoOpRowReason, PatchError
    patch_date.py    PatchDate: a real date, the infinite past or the infinite future
    effect_model.py  Effect, ValueUpdate, ValueUpdatesTimeline
    diff_model.py    PatchDiff and its parts
    warning_model.py the warnings about one patch
  parser.py          reads a CSV file into a PatchText, parses the PatchText into a Patch
  effect.py          builds the Effect of a Patch: the timelines
  diff.py            compares two Patches, returns a PatchDiff (columns, effect, warnings)
  patch_warnings.py  finds the warnings of one Patch
  report.py          renders a PatchDiff as plain text
  __main__.py        command line
tests/unit           one module at a time
tests/integration    from CSV text to a PatchDiff, all the date cases
tests/e2e            whole files through the command line, one folder per case
samples/             the sample patches that came with the task
```

## User interface considerations

### The grammar

<p align="right"><i>"One of the major problems encountered in time travel is ... one of grammar"</i><br />
    Douglas Adams</p>

In this patch tool we are dealing with at least three processes that happen at different times:

* The process described by the database to which the patches are applied. Each record has a date for a reason.
* The process of applying the patch
* The process of comparing the patches

So when we say "a key was updated" it immediately becomes confusing: was it updated in the original database? Was it updated during the patch application process? Or perhaps the values belonging to that key were updated? Or perhaps the **way** these values are updated has been changed between the patches?

Whatever wording you choose, it will be either confusing, verbose or both.

Current wordings like `No longer patching Issuer X` and `for dates on or after Y` were crafted after multiple iterations and reviews. They may not be perfect, but perfect is the enemy of good.

### The warnings 

The question of warnings was another tough one. On the one hand we want the user to know when things look weird. On the other hand, warnings may take up a large part of the diff, and the same warnings may repeat for both patches.

Also, some things are more suspicious than others. E.g. rows that override other rows' values are present in every example, and therefore were deemed not to deserve a warning. On the other hand, columns with no values or rows that have no effect do generate a warning.

If warnings get in the way, they can be removed via the `--no-warnings` command line argument.

### Human readable vs machine-processable

Another design tension was between human readable text and processing-friendly text. We could dispense with all the grammar and just print something YAML-like:

```
- issuer: BLA
  change: modified
  columns:
    - column: Country
      change: removed
      value: FRA
      begin_date: null
      end_date: 2024-01-31
```

instead of

```
Modified Issuer 'BLA':
    Removed Country 'FRA' for dates on or before 2024-01-31
```

However, the requirement specifically calls for the diff to be "human-friendly" because it "will be shown to users", so we are using a human-readable format.

We could easily support other output formats such as YAML, Markdown, HTML, XML or JSON. The renderer is isolated in `report.py` and is replaceable. This is where we would use OOP principles: one renderer interface, multiple implementations.

## Design notes

**Data classes and functions.** The classes in `model/` only hold data. They are frozen and have no logic, apart from a few read-only properties and lookups over their own fields, such as `Effect.get_timeline`. The collections inside them are tuples and read-only mappings. The date types are the exception. `PatchDate` is a real date, the infinite past or the infinite future. It can be compared with another `PatchDate` and can step one day forward or back. `DateRange` is a pair of `PatchDate` values, with both ends included. A blank date in the file becomes an infinite date when the file is read, so the rest of the code never checks for a missing date. Functions do the work: `load_patch`, `build_effect`, `diff_patches`, `render_diff`.

The split between data classes and functions is on purpose. The tool is a chain of steps, and each step takes values and returns a new value. A file becomes a `Patch`. A `Patch` becomes an `Effect`. Two patches become a `PatchDiff`. A `PatchDiff` becomes text. No value changes after it is created, every step has one implementation, and no value lives longer than one run. So there is no state to protect and no step that needs a second implementation, and classes with behavior would add code without any gain. Methods would also tie the data to the file formats: a `Patch.load()` method would tie `Patch` to CSV, and a `PatchDiff.to_text()` method would tie `PatchDiff` to plain text.

**Frozen dataclasses, not named tuples.** The main reason is equality. A named tuple is equal to a plain tuple with the same values, and to a named tuple of another type with the same values. A dataclass is equal only to an object of its own class, and the tests compare model objects with `==`. The second reason is access by position. A named tuple can be unpacked and indexed, and code that does so keeps running, with wrong values, when a field is added or moved. The fields of a dataclass can only be read by name.

## The comparison algorithm

A patch is a CSV file with the columns `BeginDate` and `EndDate`, a key column and value columns. Each row sets values for one key on one date range.

A plain text diff of two patch files is of little use. Rows and columns can often be reordered without changing what a patch does, and two patches that look different can do the same thing. So the tool compares what the two patches **do** (the effect), not how they are written.

### Calculating the effect

Rows of a patch are applied top to bottom, so when two rows set the same column for the same key and date, the later row wins. An important property is that the effects for different keys are completely independent and never overlap, since one row can affect only one key.

The effect (`Effect`) is a collection of **timelines** keyed by key and column. A **timeline** (`ValueUpdatesTimeline`) is a list of value updates. Each value update contains a date range and a value.

For illustration, let's consider a practical example.

Suppose we have the following patch:

```
BeginDate  EndDate    Key  Country Analyst
                      AMZN FRA
20240110   20240120   AMZN USA      Bob
           20250428   GOOG MEX      George
```

It would generate the following effect:

```
Key=AMZN
    Country
        (begin: INFINITE_PAST, end: 20240109,        value: FRA)
        (begin: 20240110,      end: 20240120,        value: USA)
        (begin: 20240121,      end: INFINITE_FUTURE, value: FRA)
    Analyst
        (begin: 20240110,      end: 20240120,        value: Bob)
Key=GOOG
    Country
        (begin: INFINITE_PAST, end: 20250428,        value: MEX)
    Analyst
        (begin: INFINITE_PAST, end: 20250428,        value: George)
```

Effect generation is implemented by the `build_effect()` function.

### Calculating the difference between effects

Difference between effects is calculated key by key, in sorted key order, and column by column within a key, in `_get_effect_diffs()`.

The function that handles one column of one key is `_column_diffs()`.

The first action is to gather the dates from the value updates of both patches, and split them into non-overlapping ranges: `split_into_non_overlapping_ranges()`.

Let's consider two patches below. Only a single key matters for this example, all other keys are compared separately.

Patch1:

```
BeginDate  EndDate    Key  Country Analyst
                      AMZN FRA
20240110   20240120   AMZN USA      Bob
           20250428   GOOG MEX      George
```

Patch2:

```
BeginDate  EndDate    Key  Country Analyst
           20240105   AMZN MEX       Bob
20240106              AMZN MEX       Mike
```

The timelines of the first patch for AMZN are:

```
Key=AMZN
    Country
        (begin: INFINITE_PAST, end: 20240109,        value: FRA)
        (begin: 20240110,      end: 20240120,        value: USA)
        (begin: 20240121,      end: INFINITE_FUTURE, value: FRA)
    Analyst
        (begin: 20240110,      end: 20240120,        value: Bob)
```

The timelines of the second patch are:

```
Key=AMZN
    Country
        (begin: INFINITE_PAST, end: INFINITE_FUTURE, value: MEX)
    Analyst
        (begin: INFINITE_PAST, end: 20240105,        value: Bob)
        (begin: 20240106,      end: INFINITE_FUTURE, value: Mike)
```

Note that both rows of Patch2 set Country to MEX, on adjacent dates, and the timeline has a single record for them. Value updates that follow each other with the same value are joined.

Once we've got the timelines, we calculate a set of "interesting" dates from both, column by column. An "interesting" date is defined as the begin of a range, or the day following the end of a range. See `split_into_non_overlapping_ranges()`. The interesting dates of Country are:

`INFINITE_PAST, 20240110, 20240121, INFINITE_FUTURE`

The interesting dates of Analyst are:

`INFINITE_PAST, 20240106, 20240110, 20240121, INFINITE_FUTURE`

Corresponding non-overlapping ranges are:

```
Country                        Analyst
(INFINITE_PAST, 20240109),     (INFINITE_PAST, 20240105),
(20240110, 20240120),          (20240106, 20240109),
(20240121, INFINITE_FUTURE)    (20240110, 20240120),
                               (20240121, INFINITE_FUTURE)
```

Then we assemble the diffs of each column by date in `_column_diffs()`:

```
BeginDate      EndDate          Column   OldValue  NewValue
INFINITE_PAST  20240109         Country  FRA       MEX
20240110       20240120         Country  USA       MEX
20240121       INFINITE_FUTURE  Country  FRA       MEX
INFINITE_PAST  20240105         Analyst  (none)    Bob
20240106       20240109         Analyst  (none)    Mike
20240110       20240120         Analyst  Bob       Mike
20240121       INFINITE_FUTURE  Analyst  (none)    Mike
```

This is already the final order: the columns in the column order of the old patch, and the diffs of each column by date. The date ranges of one column do not overlap, the date ranges of two columns can.

This structure is then converted to output text by `_change_lines()` as follows. A value that only the new patch sets is `Added`, a value that both patches set is `Changed`:

```
Modified Key 'AMZN':
    Changed Country from 'FRA' to 'MEX' for dates on or before 2024-01-09
    Changed Country from 'USA' to 'MEX' for dates between 2024-01-10 and 2024-01-20
    Changed Country from 'FRA' to 'MEX' for dates on or after 2024-01-21
    Added Analyst 'Bob' for dates on or before 2024-01-05
    Added Analyst 'Mike' for dates between 2024-01-06 and 2024-01-09
    Changed Analyst from 'Bob' to 'Mike' for dates between 2024-01-10 and 2024-01-20
    Added Analyst 'Mike' for dates on or after 2024-01-21
```

#### Handling multiple columns

Note that in this version we handle each column separately, and the report lists the changes of a key column by column.

An earlier version handled all columns of a key at once and did not do grouping. This prevented overlapping date ranges, but led to quadratic behavior. The timeline would be split at "interesting" dates for all columns in all rows combined, generating about N²/2 reports for N changes, and was therefore rejected.

### Columns

- If the two patches have different key columns, the tool stops with an error, because the patches cannot be compared.
- The order of the value columns is ignored.
- A value column that is in one patch only gets one line in the report, for example `Added column Analyst` or `Removed column Industry`.
- The values of such a column are also listed key by key, like the values of any other column: `Added` if only the new patch has the column, `Removed` if only the old patch has it. So removing a column that has a value for 1,000 keys gives 1,000 lines. These are 1,000 real changes, and the column line above them says where they come from.

### Warnings

A warning is about one patch, not about the difference between the two patches. The tool checks both patches, and each patch has its own subsection. So a problem that was already in the old patch is listed as well. A row warning is followed by the rows it is about, printed in full with their key. There are three kinds of warnings:

- **A row that does nothing.** The key is blank, BeginDate is after EndDate, or the row has no values.
- **A redundant row.** Later rows overwrite all its values on every date. The warning names those later rows.
- **An empty column.** The column has no values. A column that has values, none of which takes effect, gets no warning of its own: all its values sit in rows that do nothing, and those rows already have a warning.

Two rows of one key that set the same column on the same dates are not a warning, as long as the earlier row still sets something. A value for all dates and then another value from some date on is the normal way to write a patch.

### Stable output

The same two files always give the same report. Keys are sorted alphabetically (plain text order, upper case before lower case). The changes of one key are sorted by column, in the column order of the old patch, with the columns that only the new patch has last, then by date. Warnings are sorted by row number. In a warning, the columns follow the column order of the patch the warning is about. Removed columns are listed before added columns, and both are sorted by name.

A value from the files is printed in single quotes, for example `'USA'`, so it is clear where the value begins and ends. Dates and column names have no quotes.

## Testing details

The tests are in three folders:

```
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest tests/e2e
```

The three kinds of tests differ in what a test starts from, how much of the tool runs, and what the test checks:

|             | Starts from                                           | What runs                                                  | What is checked                                              |
| ----------- | ----------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| Unit        | a few lines of CSV text, or objects built in the test | one module                                                 | one rule of that module: a parsed row, a timeline, a diff, a warning, one part of the report |
| Integration | CSV text                                              | the parser, the effect module and the diff module together | the `PatchDiff` data, with no report text                    |
| End to end  | files on disk                                         | the whole tool, through the command line                   | the printed report or error message, and the exit code       |

A unit test is not strictly isolated. Most unit tests build their input from CSV text with the real parser, because that is the shortest way to write a patch. What makes them unit tests is that each one checks one rule of one module. An integration test checks a whole scenario, such as one row overriding part of another, from the text to the diff. An end-to-end test runs the tool the way a user does, and checks what it prints.

- **`tests/unit`** tests one module at a time: the parser, the date types, the effect of a patch, the diff, the warnings and the report text.
- **`tests/integration`** runs CSV text through the parser, the effect module and the diff module together, and checks the resulting `PatchDiff`. `test_date_overrides.py` has one named test for every way the date ranges of two rows can sit against each other: one date range inside the other, overlapping on the left or on the right, sharing a single day, adjacent, or with a gap between the two. `test_day_by_day.py` checks the same date cases by brute force.
- **`tests/e2e`** runs whole files through the command line. Every folder under `tests/e2e/cases/success` and `tests/e2e/cases/error` is one case with `old.csv` and `new.csv`. A case in `tests/e2e/cases/success` also has `expected.txt`, the report that the tool must print. A case in `tests/e2e/cases/error` has `expected_error.txt`, the error message the tool must print. The sample patches that came with the task are four of the success cases. To add a case, add a folder.

### Test strategy

The hard part of the tool is the date logic: which row wins on which dates. The part that changes most often is the wording of the report. The tests keep the two apart, so that a change to one does not break the tests of the other.

- **End-to-end tests cover situations, not date logic.** An end-to-end test compares the whole report as text. If every date case were tested that way, each case would repeat the file names and the warnings, and one change of wording would break all of them. So the date cases stay in the integration tests, and each end-to-end case is one situation a user runs into: the sample patches, a renamed column, a moved date, a key whose only row stops doing anything, all rows deleted, and the input errors. They pin the wording of the report for that situation, and they prove that the parts are wired together.
- **The date logic is tested on data, not on text.** `diff_patches` returns a `PatchDiff`, which holds the date ranges and the values as data. The integration tests start from CSV text, so they go through the real parser, and they compare that data. No report wording is involved.
- **Every date case has a named test, and a brute-force test backs them up.** The named tests in `test_date_overrides.py` document the cases one by one. `test_day_by_day.py` does not rely on that list being complete. It takes every pair of date ranges that can be built from a few dates. For each pair, it applies the rows to every single day in the slowest and simplest way. The effects diff must agree with the result. To make sure the brute-force test can fail, the date logic was broken on purpose in four ways: end date not included, cut one day late, earlier row wins, adjacent updates not joined. Each break made tests fail.
- **The renderer is divided into parts.** `render_diff` puts together three parts, and each part has its own function: the title, the differences and the warnings. Most report tests check one part, so a change of wording in the warnings breaks only the tests of the warnings. Putting the parts together is trivial, and one test covers it.
- **Test names say what happens and when,** for example `test_new_row_replaces_last_day_of_old_row_when_it_begins_on_the_day_old_row_ends`. A failing test says what broke before anyone opens the file.

## Alternatives considered and rejected

- **Markdown as the output format.** An earlier version printed Markdown. Every value had to be in backticks, so that a value like `A_B_C` shows as typed, and the backticks, `#` and `**` marks are confusing for a user who reads the report in a terminal. The report is plain text now. Markdown can be added as an option: it needs a second report module and no other change.
- **A shape diff.** An earlier version had a second diff next to the effects diff. For every key whose rows were not the same in the two patches, it printed the rows of both patches, under "Different effects" or "Same effect". It showed edits that change nothing, such as a redundant row that was removed. It was dropped for multiple reasons:

  - the task asks how the application of the patch changes, not for a text diff.
  - every real change was reported twice.
  - a plain text diff of the two files sorted by key shows the same thing.
  - single responsibility principle: every tool should do one thing and do it well.
- **One line for an added or removed column, and nothing about its values.** An earlier version printed only the column line. It was short, but a key whose only change was a value in that column was not in the report at all. Now the column line is still there, and the values are listed key by key like any other change.
- **Row numbers in the differences.** An earlier version printed the row every value came from, for example `'Bob' (row 5) => 'Sally' (row 5)`. The two numbers are rows of two different files, which was confusing, and the example in the task has no row numbers. Row numbers are now printed only in warnings, where they point into one file. The timelines no longer keep the rows, which made them simpler.
- **A warning for overlapping rows.** An earlier version warned about every two rows of one key that set the same column on the same dates. A value for all dates and then another value from some date on is the normal way to write a patch, so every sample patch got such warnings, and they hid the real ones.
- **Optimizing quadratic behavior on large keys.** The current algorithm is quadratic on keys with many rows, but linear with respect to the number of keys. The assumption is that the number of rows per key is generally small (10-20 at most), so it is not an issue. 100 rows of one key take under 0.1 second, and 1,000 rows of one key take about 1.5 seconds.

  One source of the quadratic behavior on a large key is `find_value_on_day()` performing a linear search. We could replace it with binary search, but it would complicate the code for no obvious gain if our assumptions are correct. Another quadratic step is building the timeline of a key.

  If we discover that a large number of rows per key is the norm, we should reconsider.

## Known issues

- **A line break inside a cell is lost in the report.** The report prints a value on one line, with every line break replaced by a space. If the only change in a value is a line break, the report shows the same text twice: `Changed Sector from 'Information Technology' to 'Information Technology'`.
- **Row numbers follow file text lines.** The report counts lines, not rows. It is technically possible for a row to contain a newline character, so it will span multiple lines of text. In that case reported row numbers and row numbers shown by Excel will diverge.
- **An unclosed quote is not an error.** From the opening quote on, the rest of the file is read as one value. The report then shows that long value as a change, and the rows after it as removed.
- **A quote inside a value is not escaped.** `O'Brien` is printed as `'O'Brien'`.
- **Non-ASCII digits are accepted in dates.** `٢٠٢٤٠٢٠١`, a string of Eastern Arabic numerals, is read as 20240201.

## Left as it is, on purpose

The code was reviewed several times, both manually, and by AI agents. The following points came up and were left as they are, for the reasons given.

- **Warnings are printed for both patches.** A reviewer found that a problem in the old patch is not something the user just did. Both patches matter, though. A row with reversed dates in the old patch explains a difference just as well as one in the new patch, and the old patch is the version that is in the system now.
- **An empty column is a warning.** Every sample patch has an empty `Industry` column, so every sample run warns about it twice. It is still worth a look: a column with no values does nothing, whether it was always empty or someone cleared it.
- **The same warning can appear under both patches.** When the user did not touch the rows in question, the old and the new patch get the same warning. Filtering out warnings that both patches share would need matching rows between two files whose row numbers have shifted, and that is more code than the problem is worth.
- **Keys are sorted alphabetically, by code point.** File order would depend on which file, and would change when rows of different keys are moved around, which the task says is not a difference. Code point order puts `'10'` before `'9'` and upper case before lower case. A natural sort was not worth the code for keys that are usually tickers.
- **The values of an added or removed column are listed key by key.** The task asks to highlight an added or removed column succinctly, and the column line does that. Leaving the values out hid a key whose only change was a value in that column. See "Columns".
- **A renamed column shows as one column removed and one added.** Detecting a rename would mean guessing that two columns with the same values are the same column. The report says what it knows.
- **A moved date shows as a removed or added value.** Moving the BeginDate of CAT's row from January 1 to February 1 prints `Removed Analyst 'Emily' for dates between 2024-01-01 and 2024-01-31`. The tool compares what the patches do, not what the user typed, and on those dates the new patch indeed no longer sets the analyst.
- **`Now patching` and `No longer patching` are about what the patch does, not about rows.** `No longer patching Issuer 'CAT'` is printed when the new patch sets no value for CAT, even if CAT still has a row, for example one with reversed dates. The warning under it says why.
- **A file with the wrong delimiter gets the error "column 'BeginDate' is missing".** A semicolon or tab separated file is read as one column. The error is true, and the task says the files are CSV.
- **The fallback to the local encoding is silent.** If it worked, a note would be noise. If it did not, the user sees the error, or wrong letters in the report.
- **There is no Python API.** The tool is a command line program. The function that `__main__.py` calls is private, and `patchdiff/__init__.py` exports nothing.
- **The exit code is 0 whether or not the patches differ.** The exit code says whether the tool could compare the files. Scripts that need to know about differences can look at the report.
- **The run time is quadratic in the number of rows of one key.** See "Alternatives considered and rejected".

## Not in scope

- Excel input.
- Additional output formats like JSON.
- Analyzing the textual difference between patches.
