"""Contiguous seat bonding: aisle columns break runs; holds conflict on overlap.

Couple pairs: a registered pair binds two adjacent columns in one row. Any
block that touches a pair must take both cells (整对纳入) or neither (整对跳过)
— a block may never cover just one half of a pair.
"""

from __future__ import annotations

from dataclasses import dataclass


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
class CouplePairSpan:
    row: int
    left_col: int  # pair occupies left_col and left_col + 1

    @property
    def right_col(self) -> int:
        return self.left_col + 1


# Failure reasons for a block search that found nothing.
NO_CONTIGUOUS = "no_contiguous"  # 普通连续空座不足
HALF_PAIR = "half_pair"  # 半对占用：长度够但每种排法都要拆开一对情侣座


@dataclass(frozen=True)
class BlockSearch:
    block: HoldSpan | None
    reason: str | None = None  # None when block is found


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


def _segments(free_cols: list[int]) -> list[tuple[int, int]]:
    """Group sorted free columns into consecutive inclusive (start, end) segments."""
    segs: list[tuple[int, int]] = []
    start: int | None = None
    prev: int | None = None
    for col in free_cols:
        if start is None:
            start = col
        elif prev is not None and col != prev + 1:
            segs.append((start, prev))
            start = col
        prev = col
    if start is not None and prev is not None:
        segs.append((start, prev))
    return segs


def _splits_pair(start_col: int, end_col: int, pairs: list[CouplePairSpan]) -> bool:
    """True if the inclusive block covers exactly one cell of any couple pair."""
    for p in pairs:
        left_in = start_col <= p.left_col <= end_col
        right_in = start_col <= p.right_col <= end_col
        if left_in != right_in:
            return True
    return False


def find_block_in_row(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    pairs: list[CouplePairSpan],
    row: int,
    party_size: int,
) -> BlockSearch:
    """Leftmost contiguous block of party_size in a row, never splitting a pair.

    On failure the reason is HALF_PAIR when a long-enough gap existed but every
    placement would have split a couple pair, otherwise NO_CONTIGUOUS.
    """
    if party_size <= 0:
        return BlockSearch(None, NO_CONTIGUOUS)
    taken = occupied_cols(holds, row)
    row_pairs = [p for p in pairs if p.row == row]
    blocked_by_pair = False
    for run_start, run_end in contiguous_runs(row_cells):
        free = [c for c in range(run_start, run_end + 1) if c not in taken]
        for seg_start, seg_end in _segments(free):
            if seg_end - seg_start + 1 < party_size:
                continue
            for start in range(seg_start, seg_end - party_size + 2):
                end = start + party_size - 1
                if _splits_pair(start, end, row_pairs):
                    blocked_by_pair = True
                    continue
                return BlockSearch(HoldSpan(row=row, start_col=start, end_col=end))
    return BlockSearch(None, HALF_PAIR if blocked_by_pair else NO_CONTIGUOUS)


def find_block_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    pairs: list[CouplePairSpan],
    party_size: int,
) -> BlockSearch:
    reason: str = NO_CONTIGUOUS
    for row in sorted(seats_by_row.keys()):
        res = find_block_in_row(seats_by_row[row], holds, pairs, row, party_size)
        if res.block is not None:
            return res
        if res.reason == HALF_PAIR:
            reason = HALF_PAIR
    return BlockSearch(None, reason)


def find_contiguous_block(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    row: int,
    party_size: int,
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row (no pairs)."""
    return find_block_in_row(row_cells, holds, [], row, party_size).block


def find_bond_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
) -> HoldSpan | None:
    return find_block_across_rows(seats_by_row, holds, [], party_size).block


def conflicts_with(existing: list[HoldSpan], candidate: HoldSpan) -> list[HoldSpan]:
    hits: list[HoldSpan] = []
    for h in existing:
        if h.row != candidate.row:
            continue
        if h.end_col < candidate.start_col or candidate.end_col < h.start_col:
            continue
        hits.append(h)
    return hits
