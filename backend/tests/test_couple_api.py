"""API-level couple-pair behaviour: CRUD validation, half-pair conflict branch,
whole-pair hold success with couple columns on the order."""

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.models import Hall, Showtime


def _make_showtime(rows=8, cols=12, aisles="5,6") -> tuple[int, int]:
    db = SessionLocal()
    try:
        hall = Hall(name="测试厅", rows=rows, cols=cols, aisle_cols=aisles)
        db.add(hall)
        db.flush()
        st = Showtime(
            hall_id=hall.id,
            film_title="测试片",
            start_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(st)
        db.commit()
        return hall.id, st.id
    finally:
        db.close()


def _make_couple_hall() -> tuple[int, int]:
    """单排 6 座无过道、中央一对情侣位（3-4）—— 与种子的情侣厅同构。"""
    hall_id, st_id = _make_showtime(rows=1, cols=6, aisles="")
    return hall_id, st_id


def test_pair_crud_roundtrip(client):
    hall_id, _ = _make_showtime()
    created = client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": 9})
    assert created.status_code == 201, created.text
    pair = created.json()
    assert pair["end_col"] == 10

    listed = client.get(f"/api/halls/{hall_id}/pairs").json()
    assert [(p["row"], p["start_col"], p["end_col"]) for p in listed] == [(6, 9, 10)]

    moved = client.put(f"/api/pairs/{pair['id']}", json={"row": 7, "start_col": 2})
    assert moved.status_code == 200
    assert moved.json()["row"] == 7 and moved.json()["start_col"] == 2

    assert client.delete(f"/api/pairs/{pair['id']}").status_code == 204
    assert client.get(f"/api/halls/{hall_id}/pairs").json() == []


def test_pair_must_not_cross_aisle(client):
    hall_id, _ = _make_showtime()
    # 4-5 与 5-6 都压到过道列 5/6；12-13 超出厅宽
    for start_col in (4, 5, 6, 12):
        res = client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": start_col})
        assert res.status_code == 400, (start_col, res.text)
    ok = client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": 9})
    assert ok.status_code == 201


def test_pair_rejects_overlap(client):
    hall_id, _ = _make_showtime()
    assert client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": 9}).status_code == 201
    for start_col in (8, 9, 10):  # 与 9-10 共用格子
        res = client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": start_col})
        assert res.status_code == 409, (start_col, res.text)
    assert client.post(f"/api/halls/{hall_id}/pairs", json={"row": 6, "start_col": 11}).status_code == 201


def test_hold_half_pair_failure_writes_distinguishable_conflict(client):
    hall_id, st_id = _make_couple_hall()
    client.post(f"/api/halls/{hall_id}/pairs", json={"row": 1, "start_col": 3})

    # 人数 3：落窗 1-3 切开情侣对（3-4）→ 半对失败，原因可与普通不足区分
    res = client.post("/api/holds", json={"showtime_id": st_id, "party_size": 3})
    assert res.status_code == 409
    conflicts = client.get("/api/conflicts").json()
    half = [c for c in conflicts if c["kind"] == "half_pair"]
    assert half, conflicts
    assert "3-4" in half[0]["reason"] and "第1排" in half[0]["reason"]
    assert not client.get("/api/holds").json()  # 失败不得写入任何持座

    # 人数 12：普通连续空座不足，kind 必须可区分
    res = client.post("/api/holds", json={"showtime_id": st_id, "party_size": 12})
    assert res.status_code == 409
    kinds = {c["kind"] for c in client.get("/api/conflicts").json()}
    assert kinds == {"half_pair", "no_contiguous"}


def test_hold_whole_pair_success_marks_order(client):
    hall_id, st_id = _make_couple_hall()
    client.post(f"/api/halls/{hall_id}/pairs", json={"row": 1, "start_col": 3})

    # 人数 4：落窗 1-4 整对纳入两格
    res = client.post("/api/holds", json={"showtime_id": st_id, "party_size": 4})
    assert res.status_code == 200, res.text
    hold = res.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 1, 4)
    assert hold["couple_cols"] == [3]

    # 持座列表能看出本单含情侣对及列号
    listed = client.get("/api/holds").json()
    assert listed[0]["couple_cols"] == [3]

    # 座位图标出成对格子且两格均被占用
    cells = client.get(f"/api/seatmap/{st_id}").json()["cells"]
    by_pos = {(c["row"], c["col"]): c for c in cells}
    assert by_pos[(1, 3)]["pair_id"] is not None
    assert by_pos[(1, 4)]["pair_id"] == by_pos[(1, 3)]["pair_id"]
    assert by_pos[(1, 3)]["occupied"] and by_pos[(1, 4)]["occupied"]


def test_hold_skips_pair_when_not_needed(client):
    hall_id, st_id = _make_couple_hall()
    client.post(f"/api/halls/{hall_id}/pairs", json={"row": 1, "start_col": 3})

    # 人数 2：左侧 1-2 即可满足，整对跳过，本单不含情侣对
    res = client.post("/api/holds", json={"showtime_id": st_id, "party_size": 2})
    assert res.status_code == 200, res.text
    hold = res.json()
    assert (hold["start_col"], hold["end_col"]) == (1, 2)
    assert hold["couple_cols"] == []
