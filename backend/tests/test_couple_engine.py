from app.services.bond_engine import (
    HALF_PAIR,
    NO_CONTIGUOUS,
    CouplePairSpan,
    HoldSpan,
    SeatCell,
    find_block_across_rows,
    find_block_in_row,
)

PAIR = CouplePairSpan(row=1, left_col=5)  # pair on columns 5-6


def _row(cols, aisles=()):
    return [SeatCell(row=1, col=c, is_aisle=(c in aisles)) for c in cols]


def test_pair_skipped_when_block_fits_elsewhere():
    res = find_block_in_row(_row(range(1, 10)), [], [PAIR], 1, 4)
    assert res.block == HoldSpan(row=1, start_col=1, end_col=4)
    assert res.reason is None


def test_pair_taken_whole_when_block_covers_it():
    # party 5: [1-5] would split the pair, so the block slides to [2-6]
    res = find_block_in_row(_row(range(1, 10)), [], [PAIR], 1, 5)
    assert res.block == HoldSpan(row=1, start_col=2, end_col=6)


def test_single_seat_cannot_take_half_a_pair():
    cells = _row(range(1, 10))
    holds = [HoldSpan(row=1, start_col=1, end_col=4), HoldSpan(row=1, start_col=7, end_col=9)]
    res = find_block_in_row(cells, holds, [PAIR], 1, 1)
    assert res.block is None
    assert res.reason == HALF_PAIR
    # the whole pair is still bookable as a pair
    res2 = find_block_in_row(cells, holds, [PAIR], 1, 2)
    assert res2.block == HoldSpan(row=1, start_col=5, end_col=6)


def test_half_pair_reason_when_partner_already_held():
    # free segments [1-5] and [7-9]; col 5 is only half a pair (6 is held)
    cells = _row(range(1, 10))
    holds = [HoldSpan(row=1, start_col=6, end_col=6)]
    res = find_block_in_row(cells, holds, [PAIR], 1, 5)
    assert res.block is None
    assert res.reason == HALF_PAIR


def test_ordinary_shortage_reason_is_distinguishable():
    # same layout, but party 6 fits nowhere even ignoring the pair
    cells = _row(range(1, 10))
    holds = [HoldSpan(row=1, start_col=6, end_col=6)]
    res = find_block_in_row(cells, holds, [PAIR], 1, 6)
    assert res.block is None
    assert res.reason == NO_CONTIGUOUS


def test_across_rows_surfaces_half_pair_reason():
    seats = {
        1: _row(range(1, 5)),  # too short: ordinary shortage
        2: [SeatCell(row=2, col=c) for c in range(1, 10)],
    }
    holds = [HoldSpan(row=2, start_col=6, end_col=6)]
    pairs = [CouplePairSpan(row=2, left_col=5)]
    res = find_block_across_rows(seats, holds, pairs, 5)
    assert res.block is None
    assert res.reason == HALF_PAIR


def test_across_rows_finds_whole_pair_block():
    seats = {1: [SeatCell(row=1, col=c) for c in range(1, 10)]}
    res = find_block_across_rows(seats, [], [PAIR], 5)
    assert res.block == HoldSpan(row=1, start_col=2, end_col=6)
