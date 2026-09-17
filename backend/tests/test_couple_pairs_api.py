"""API-level tests for couple pairs: CRUD, half-pair failure branch, whole-pair success."""


def _showtime_id(client, title):
    shows = client.get("/api/showtimes").json()
    return next(s["id"] for s in shows if s["film_title"] == title)


def _hall_id(client, name):
    halls = client.get("/api/halls").json()
    return next(h["id"] for h in halls if h["name"] == name)


def test_half_pair_failure_has_distinct_reason(client):
    sid = _showtime_id(client, "半对练习场")
    # party 5: the only 5-long gap [1-5] ends on half of the pair (6 is held)
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 5})
    assert r.status_code == 409
    assert "半对" in r.json()["detail"]

    conflicts = client.get("/api/conflicts").json()
    half = [c for c in conflicts if "半对" in c["reason"]]
    assert half and half[0]["party_size"] == 5

    # party 6: fails on plain shortage — reason must stay distinguishable
    r2 = client.post("/api/holds", json={"showtime_id": sid, "party_size": 6})
    assert r2.status_code == 409
    assert "半对" not in r2.json()["detail"]
    reasons = [c["reason"] for c in client.get("/api/conflicts").json()]
    assert any("无足够连续空座" in x for x in reasons)


def test_whole_pair_success_occupies_both_cells(client):
    sid = _showtime_id(client, "整对练习场")
    r = client.post("/api/holds", json={"showtime_id": sid, "party_size": 5})
    assert r.status_code == 200
    body = r.json()
    assert (body["row"], body["start_col"], body["end_col"]) == (1, 2, 6)
    assert body["couple_cols"] == [5, 6]

    # the holds list exposes the couple columns for this order
    holds = client.get("/api/holds").json()
    mine = next(h for h in holds if h["id"] == body["id"])
    assert mine["couple_cols"] == [5, 6]

    # both pair cells are now occupied on the seatmap
    cells = client.get(f"/api/seatmap/{sid}").json()["cells"]
    by = {(c["row"], c["col"]): c for c in cells}
    assert by[(1, 5)]["occupied"] and by[(1, 6)]["occupied"]
    assert by[(1, 5)]["couple"] and by[(1, 6)]["couple"]
    assert not by[(1, 4)]["couple"]


def test_pair_crud_and_registration_rules(client):
    hall = _hall_id(client, "一号厅")  # aisles at columns 5,6

    r = client.post(f"/api/halls/{hall}/pairs", json={"row": 8, "left_col": 8})
    assert r.status_code == 201
    pair = r.json()
    assert pair["right_col"] == 9
    assert pair["label"] == "情侣座"

    pairs = client.get(f"/api/halls/{hall}/pairs").json()
    assert [p["id"] for p in pairs] == [pair["id"]]

    # a pair may not straddle or touch an aisle column
    assert client.post(f"/api/halls/{hall}/pairs", json={"row": 8, "left_col": 4}).status_code == 409
    assert client.post(f"/api/halls/{hall}/pairs", json={"row": 8, "left_col": 6}).status_code == 409
    # overlapping an existing pair is rejected
    assert client.post(f"/api/halls/{hall}/pairs", json={"row": 8, "left_col": 9}).status_code == 409
    # out-of-range positions are rejected
    assert client.post(f"/api/halls/{hall}/pairs", json={"row": 9, "left_col": 1}).status_code == 422
    assert client.post(f"/api/halls/{hall}/pairs", json={"row": 8, "left_col": 12}).status_code == 422

    r = client.put(f"/api/pairs/{pair['id']}", json={"row": 7, "left_col": 2, "label": "双人座"})
    assert r.status_code == 200
    assert r.json()["row"] == 7
    assert r.json()["label"] == "双人座"

    assert client.delete(f"/api/pairs/{pair['id']}").status_code == 204
    assert client.get(f"/api/halls/{hall}/pairs").json() == []
    assert client.delete(f"/api/pairs/{pair['id']}").status_code == 404


def test_seeded_couple_hall_marks_pair_cells(client):
    sid = _showtime_id(client, "整对练习场")
    cells = client.get(f"/api/seatmap/{sid}").json()["cells"]
    couple_cols = sorted(c["col"] for c in cells if c["couple"])
    assert couple_cols == [5, 6]
