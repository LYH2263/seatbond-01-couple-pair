"""Contiguous seat bonding: aisle columns break runs; holds conflict on overlap.

Couple pairs (情侣对): a pair binds two adjacent columns in one row and is
atomic for locking — a hold either covers the whole pair or none of it.
When no block fits, the failure is classified so callers can distinguish
"only half a pair left" (half_pair) from ordinary "not enough contiguous
seats" (no_contiguous).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class SeatCell:
    row: int
    col: int
    is_aisle: bool = False


@dataclass(frozen=True)
class HoldSpan:
    row: int
    start_col: int
    end_col: int  # inclusive


@dataclass(frozen=True)
class PairUnit:
    """A couple pair: occupies (row, start_col) and (row, start_col + 1)."""

    row: int
    start_col: int

    @property
    def end_col(self) -> int:
        return self.start_col + 1


class BondFailure(str, Enum):
    NO_CONTIGUOUS = "no_contiguous"  # 普通连续空座不足
    HALF_PAIR = "half_pair"  # 只剩半对情侣座可落座


@dataclass(frozen=True)
class BondResult:
    span: HoldSpan | None = None
    failure: BondFailure | None = None
    # (row, pair_start_col) of every couple pair that blocked a would-be window
    cuts: tuple[tuple[int, int], ...] = field(default_factory=tuple)


def contiguous_runs(row_cells: list[SeatCell]) -> list[tuple[int, int]]:
    """Return inclusive (start_col, end_col) runs of non-aisle seats, broken by aisles."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    prev_col: int | None = None
    for cell in sorted(row_cells, key=lambda c: c.col):
        if cell.is_aisle:
            if start is not None and prev_col is not None:
                runs.append((start, prev_col))
            start = None
            prev_col = None
            continue
        if start is None:
            start = cell.col
        elif prev_col is not None and cell.col != prev_col + 1:
            runs.append((start, prev_col))
            start = cell.col
        prev_col = cell.col
    if start is not None and prev_col is not None:
        runs.append((start, prev_col))
    return runs


def occupied_cols(holds: list[HoldSpan], row: int) -> set[int]:
    cols: set[int] = set()
    for h in holds:
        if h.row != row:
            continue
        for c in range(h.start_col, h.end_col + 1):
            cols.add(c)
    return cols


def _free_segments(row_cells: list[SeatCell], taken: set[int]) -> list[tuple[int, int]]:
    """Maximal consecutive free column segments inside the aisle-broken runs."""
    segments: list[tuple[int, int]] = []
    for start, end in contiguous_runs(row_cells):
        free = [c for c in range(start, end + 1) if c not in taken]
        seg_start: int | None = None
        prev: int | None = None
        for col in free:
            if seg_start is None:
                seg_start = col
            elif prev is not None and col != prev + 1:
                segments.append((seg_start, prev))
                seg_start = col
            prev = col
        if seg_start is not None and prev is not None:
            segments.append((seg_start, prev))
    return segments


def _pair_cuts(seg_start: int, span_end: int, pair_starts: set[int]) -> list[int]:
    """Pair starts whose two cells would be split by the window [seg_start, span_end].

    A contiguous window splits a pair (p, p+1) iff it contains exactly one cell:
    p == span_end (first half in, second half out) or p + 1 == seg_start
    (second half in, first half out — e.g. the mate is already held).
    """
    return sorted(p for p in pair_starts if p == span_end or p + 1 == seg_start)


def find_bond_block(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    row: int,
    party_size: int,
    pairs: list[PairUnit] | tuple[PairUnit, ...] = (),
) -> BondResult:
    """Leftmost contiguous block of party_size in a row, couple pairs atomic.

    Per free segment the window starts at the segment's left edge (same as the
    plain search). If that window would slice a couple pair, the segment is
    rejected — the pair is never split — and the search moves to the next
    segment. Failure is HALF_PAIR when at least one segment was rejected only
    because of a pair cut, otherwise NO_CONTIGUOUS.
    """
    if party_size <= 0:
        return BondResult(failure=BondFailure.NO_CONTIGUOUS)
    taken = occupied_cols(holds, row)
    pair_starts = {p.start_col for p in pairs if p.row == row}
    cuts: list[int] = []
    for seg_start, seg_end in _free_segments(row_cells, taken):
        if seg_end - seg_start + 1 < party_size:
            continue  # segment too short — ordinary capacity miss
        span_end = seg_start + party_size - 1
        hit = _pair_cuts(seg_start, span_end, pair_starts)
        if hit:
            cuts.extend(hit)
            continue  # would occupy half a pair — skip the whole pair instead
        return BondResult(span=HoldSpan(row=row, start_col=seg_start, end_col=span_end))
    if cuts:
        return BondResult(
            failure=BondFailure.HALF_PAIR,
            cuts=tuple((row, c) for c in sorted(set(cuts))),
        )
    return BondResult(failure=BondFailure.NO_CONTIGUOUS)


def search_bond(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
    pairs: list[PairUnit] | tuple[PairUnit, ...] = (),
) -> BondResult:
    """First fitting row in row order; a half-pair miss anywhere stays visible."""
    cuts: list[tuple[int, int]] = []
    saw_half_pair = False
    for row in sorted(seats_by_row.keys()):
        result = find_bond_block(seats_by_row[row], holds, row, party_size, pairs)
        if result.span is not None:
            return result
        saw_half_pair = saw_half_pair or result.failure == BondFailure.HALF_PAIR
        cuts.extend(result.cuts)
    if saw_half_pair:
        return BondResult(failure=BondFailure.HALF_PAIR, cuts=tuple(cuts))
    return BondResult(failure=BondFailure.NO_CONTIGUOUS)


def find_contiguous_block(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    row: int,
    party_size: int,
    pairs: list[PairUnit] | tuple[PairUnit, ...] = (),
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row."""
    return find_bond_block(row_cells, holds, row, party_size, pairs).span


def find_bond_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
    pairs: list[PairUnit] | tuple[PairUnit, ...] = (),
) -> HoldSpan | None:
    return search_bond(seats_by_row, holds, party_size, pairs).span


def conflicts_with(existing: list[HoldSpan], candidate: HoldSpan) -> list[HoldSpan]:
    hits: list[HoldSpan] = []
    for h in existing:
        if h.row != candidate.row:
            continue
        if h.end_col < candidate.start_col or candidate.end_col < h.start_col:
            continue
        hits.append(h)
    return hits
