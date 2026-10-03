"""Data model: what differs between two patches."""

from __future__ import annotations

from dataclasses import dataclass

from .patch_model import ColumnName, DateRange
from .warning_model import PatchWarning


@dataclass(frozen=True)
class EffectDiff:
    """One difference in what the two patches do: one key, one column, one date range.

    A value is None if the patch does not set the column on those dates.
    """

    key: str
    column: ColumnName
    dates: DateRange
    old_value: str | None
    new_value: str | None


@dataclass(frozen=True)
class PatchDiff:
    """Everything the report needs: what differs between two patches, and the warnings about each of them."""

    old_name: str
    new_name: str
    key_column: ColumnName
    columns_only_in_old: tuple[ColumnName, ...]  # sorted by name
    columns_only_in_new: tuple[ColumnName, ...]  # sorted by name
    keys_only_in_old: frozenset[str]  # keys that only the old patch sets values for
    keys_only_in_new: frozenset[str]  # keys that only the new patch sets values for
    # Sorted by key, then by column in the column order of the old patch, with the columns
    # that only the new patch has last, then by date. The date ranges of one column do not overlap.
    effect_diffs: tuple[EffectDiff, ...]
    old_warnings: tuple[PatchWarning, ...]
    new_warnings: tuple[PatchWarning, ...]
