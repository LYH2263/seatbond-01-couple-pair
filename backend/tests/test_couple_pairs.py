"""Couple-pair bonding: pairs are atomic (whole or skipped), and a failed
search must distinguish 'only half a pair left' from 'not enough seats'."""

from app.services.bond_engine import (
    BondFailure,
    HoldSpan,
    PairUnit,
    SeatCell,
    find_bond_block,
    search_bond,
)


def _row(cols, aisles=(), row=1):
    return [SeatCell(row=row, col=c, is_aisle=(c in aisles)) for c in cols]


# 一排中间一对情侣位（3-4），左右各有空座 1-2 / 5-6 —— 与种子布局同构。
PAIR = PairUnit(row=1, start_col=3)


def test_half_pair_failure_is_distinguishable():
    cells = _row(range(1, 7))
    # 人数 3：落窗 1-3 会切开情侣对（3-4），只能整对跳过 → 半对失败
    result = find_bond_block(cells, [], 1, 3, pairs=[PAIR])
    assert result.span is None
    assert result.failure == BondFailure.HALF_PAIR
    assert result.cuts == ((1, 3),)


def test_plain_shortage_is_not_half_pair():
    cells = _row(range(1, 7))
    # 人数 7 超过整段长度：普通连续空座不足，不得误报半对
    result = find_bond_block(cells, [], 1, 7, pairs=[PAIR])
    assert result.span is None
    assert result.failure == BondFailure.NO_CONTIGUOUS
    assert result.cuts == ()


def test_whole_pair_success_occupies_two_cells():
    cells = _row(range(1, 7))
    # 人数 4：落窗 1-4 整对纳入，两格都写入
    result = find_bond_block(cells, [], 1, 4, pairs=[PAIR])
    assert result.span == HoldSpan(row=1, start_col=1, end_col=4)
    assert {3, 4} <= set(range(result.span.start_col, result.span.end_col + 1))


def test_pair_skipped_whole_when_not_needed():
    cells = _row(range(1, 7))
    # 人数 2：左侧空座足够，整对跳过、不碰半格
    result = find_bond_block(cells, [], 1, 2, pairs=[PAIR])
    assert result.span == HoldSpan(row=1, start_col=1, end_col=2)


def test_single_person_cannot_take_half_a_pair():
    cells = _row(range(1, 7))
    # 1-2、5-6 已被持座，只剩情侣对（3-4）两格：1 人无法只占半对
    holds = [HoldSpan(row=1, start_col=1, end_col=2), HoldSpan(row=1, start_col=5, end_col=6)]
    result = find_bond_block(cells, holds, 1, 1, pairs=[PAIR])
    assert result.span is None
    assert result.failure == BondFailure.HALF_PAIR


def test_half_held_pair_blocks_its_free_cell():
    cells = _row(range(1, 7))
    # 其余座位全被持满，情侣对的 4 列也被占：只剩 3 列这半对，不可单格落座
    holds = [
        HoldSpan(row=1, start_col=1, end_col=2),
        HoldSpan(row=1, start_col=4, end_col=4),
        HoldSpan(row=1, start_col=5, end_col=6),
    ]
    result = find_bond_block(cells, holds, 1, 1, pairs=[PAIR])
    assert result.span is None
    assert result.failure == BondFailure.HALF_PAIR


def test_pair_cut_skips_to_next_segment():
    # 过道（5 列）断开两段；第一段落窗 1-3 切开情侣对（3-4），应整对跳过并用下一段
    cells = _row(range(1, 11), aisles={5})
    result = find_bond_block(cells, [], 1, 3, pairs=[PAIR])
    assert result.span == HoldSpan(row=1, start_col=6, end_col=8)


def test_search_across_rows_keeps_half_pair_visible():
    seats = {
        1: _row(range(1, 5), row=1),  # 整排被持满
        2: _row(range(2, 4), row=2),  # 只有一对情侣位（2-3）
    }
    holds = [HoldSpan(row=1, start_col=1, end_col=4)]
    result = search_bond(seats, holds, 1, pairs=[PairUnit(row=2, start_col=2)])
    assert result.span is None
    assert result.failure == BondFailure.HALF_PAIR
    assert result.cuts == ((2, 2),)
