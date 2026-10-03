"""Compare two patches.

The result has three parts:

- columns that are in one patch only
- effect diff: the patches do different things to the data
- warnings: rows and columns that look like a mistake

This module returns data. report.py turns it into text.
"""

from __future__ import annotations

from itertools import chain

from .effect import build_effect, find_value_on_day, split_into_non_overlapping_ranges
from .model.diff_model import EffectDiff, PatchDiff
from .model.effect_model import Effect, ValueUpdatesTimeline
from .model.patch_model import ColumnName, Patch, PatchError
from .patch_warnings import find_warnings


def diff_patches(old: Patch, new: Patch) -> PatchDiff:
    """Compare two patches. Raises PatchError if their key columns differ."""
    if old.key_column != new.key_column:
        raise PatchError(
            f"key columns differ: '{old.key_column}' in {old.path}, '{new.key_column}' in {new.path}"
        )

    old_effect, new_effect = build_effect(old), build_effect(new)
    old_keys, new_keys = old_effect.timelines_per_key_and_column.keys(), new_effect.timelines_per_key_and_column.keys()
    same_name = old.name == new.name

    return PatchDiff(
        old_name=old.path if same_name else old.name,
        new_name=new.path if same_name else new.name,
        key_column=old.key_column,
        columns_only_in_old=_columns_only_in(old, new),
        columns_only_in_new=_columns_only_in(new, old),
        keys_only_in_old=frozenset(old_keys - new_keys),
        keys_only_in_new=frozenset(new_keys - old_keys),
        effect_diffs=tuple(_get_effect_diffs(_columns_of_both_patches(old, new), old_effect, new_effect)),
        old_warnings=tuple(find_warnings(old, old_effect)),
        new_warnings=tuple(find_warnings(new, new_effect)),
    )


def _columns_of_both_patches(old: Patch, new: Patch) -> list[ColumnName]:
    """Value columns of the old patch in its column order, then the columns that only the new patch has.

    A column that is in one patch only is compared like any other column. The patch
    that does not have the column has no updates for it.
    """
    return [*old.value_columns, *(column for column in new.value_columns if column not in old.value_columns)]


def _columns_only_in(patch: Patch, other: Patch) -> tuple[ColumnName, ...]:
    """Value columns of `patch` that `other` does not have, sorted by name."""
    return tuple(sorted(set(patch.value_columns) - set(other.value_columns)))


def _get_effect_diffs(columns: list[ColumnName], old: Effect, new: Effect) -> list[EffectDiff]:
    """Effect differences for all keys, sorted by key, then by column in the given order, then by date."""
    effect_diffs = []
    for key in sorted(old.timelines_per_key_and_column.keys() | new.timelines_per_key_and_column.keys()):
        for column in columns:
            effect_diffs.extend(_column_diffs(key, column, old.get_timeline(key, column), new.get_timeline(key, column)))
    return effect_diffs


def _column_diffs(
    key: str, column: ColumnName, old_timeline: ValueUpdatesTimeline, new_timeline: ValueUpdatesTimeline
) -> list[EffectDiff]:
    """The date ranges on which one column of one key differs between the two patches, in date order.

    Two of these date ranges that follow each other with no gap never have the same old
    value and the same new value. Such a pair would need a cut between them in one of
    the timelines, and a timeline has no cut between two equal values.
    """
    effect_diffs = []
    all_updates = chain(old_timeline, new_timeline)
    # Inside one date range of the split the value does not change in either patch
    for dates in split_into_non_overlapping_ranges(update.dates for update in all_updates):
        old_value = find_value_on_day(old_timeline, dates.begin)
        new_value = find_value_on_day(new_timeline, dates.begin)
        if old_value != new_value:
            effect_diffs.append(EffectDiff(key, column, dates, old_value, new_value))
    return effect_diffs
