"""Data model: warnings about one patch.

A warning is about one patch on its own, not about the difference between two patches.
"""

from __future__ import annotations

from dataclasses import dataclass

from .patch_model import ColumnName, PatchRow


@dataclass(frozen=True)
class NoOpRowWarning:
    """Warning for a row that cannot change any data. The row knows why: PatchRow.noop_reason."""

    row: PatchRow


@dataclass(frozen=True)
class RedundantRowWarning:
    """Warning for a row whose values are all overwritten by later rows, on every date."""

    row: PatchRow
    overridden_by: tuple[PatchRow, ...]  # the later rows that override it


@dataclass(frozen=True)
class EmptyColumnWarning:
    """Warning for a column that has no values."""

    column: ColumnName


PatchWarning = NoOpRowWarning | RedundantRowWarning | EmptyColumnWarning
