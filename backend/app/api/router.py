from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ConflictLog, CouplePair, Hall, SeatHold, Showtime
from app.schemas.schemas import (
    ConflictOut,
    CouplePairOut,
    CouplePairRequest,
    HallOut,
    HoldOut,
    HoldRequest,
    SeatMapCell,
    SeatMapOut,
    ShowtimeOut,
)
from app.services.bond_engine import (
    BondFailure,
    BondResult,
    HoldSpan,
    PairUnit,
    SeatCell,
    conflicts_with,
    find_bond_block,
    search_bond,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _hall_out(h: Hall) -> HallOut:
    return HallOut(id=h.id, name=h.name, rows=h.rows, cols=h.cols, aisle_cols=_aisles(h))


def _pair_units(pairs: list[CouplePair]) -> list[PairUnit]:
    return [PairUnit(row=p.row, start_col=p.start_col) for p in pairs]


def _validate_pair_slot(
    db: Session, hall: Hall, row: int, start_col: int, exclude_id: int | None = None
) -> None:
    """A couple pair binds two adjacent columns in one row; it may not sit on or
    across an aisle column, and may not overlap another pair of the same hall."""
    end_col = start_col + 1
    if row > hall.rows:
        raise HTTPException(400, f"排号超出影厅范围（1-{hall.rows}）")
    if end_col > hall.cols:
        raise HTTPException(400, f"列号超出影厅范围（情侣对需 {start_col}-{end_col} 两列）")
    aisles = set(_aisles(hall))
    if start_col in aisles or end_col in aisles:
        raise HTTPException(400, "情侣对不得跨过道登记")
    siblings = db.scalars(select(CouplePair).where(CouplePair.hall_id == hall.id)).all()
    for p in siblings:
        if exclude_id is not None and p.id == exclude_id:
            continue
        if p.row == row and abs(p.start_col - start_col) < 2:
            raise HTTPException(
                409, f"与既有情侣对重叠：第{p.row}排 {p.start_col}-{p.end_col}列"
            )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    return [_hall_out(h) for h in db.scalars(select(Hall).order_by(Hall.id)).all()]


@api_router.get("/halls/{hall_id}/pairs", response_model=list[CouplePairOut])
def list_pairs(hall_id: int, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    return db.scalars(
        select(CouplePair)
        .where(CouplePair.hall_id == hall_id)
        .order_by(CouplePair.row, CouplePair.start_col)
    ).all()


@api_router.post("/halls/{hall_id}/pairs", response_model=CouplePairOut, status_code=201)
def create_pair(hall_id: int, body: CouplePairRequest, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    _validate_pair_slot(db, hall, body.row, body.start_col)
    pair = CouplePair(hall_id=hall.id, row=body.row, start_col=body.start_col)
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair


@api_router.put("/pairs/{pair_id}", response_model=CouplePairOut)
def update_pair(pair_id: int, body: CouplePairRequest, db: Session = Depends(get_db)):
    pair = db.get(CouplePair, pair_id)
    if not pair:
        raise HTTPException(404, "情侣对不存在")
    hall = db.get(Hall, pair.hall_id)
    assert hall
    _validate_pair_slot(db, hall, body.row, body.start_col, exclude_id=pair.id)
    pair.row = body.row
    pair.start_col = body.start_col
    db.commit()
    db.refresh(pair)
    return pair


@api_router.delete("/pairs/{pair_id}", status_code=204)
def delete_pair(pair_id: int, db: Session = Depends(get_db)):
    pair = db.get(CouplePair, pair_id)
    if not pair:
        raise HTTPException(404, "情侣对不存在")
    db.delete(pair)
    db.commit()


@api_router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(db: Session = Depends(get_db)):
    rows = db.scalars(select(Showtime).order_by(Showtime.start_at)).all()
    out = []
    for s in rows:
        hall = db.get(Hall, s.hall_id)
        out.append(
            ShowtimeOut(
                id=s.id,
                hall_id=s.hall_id,
                film_title=s.film_title,
                start_at=s.start_at,
                hall_name=hall.name if hall else None,
            )
        )
    return out


@api_router.get("/seatmap/{showtime_id}", response_model=SeatMapOut)
def seatmap(showtime_id: int, db: Session = Depends(get_db)):
    st = db.get(Showtime, showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    holds = db.scalars(select(SeatHold).where(SeatHold.showtime_id == showtime_id)).all()
    occupied: set[tuple[int, int]] = set()
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied.add((h.row, c))
    pair_cells: dict[tuple[int, int], int] = {}
    for p in db.scalars(select(CouplePair).where(CouplePair.hall_id == hall.id)).all():
        pair_cells[(p.row, p.start_col)] = p.id
        pair_cells[(p.row, p.end_col)] = p.id
    cells: list[SeatMapCell] = []
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            occ = (r, c) in occupied
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=c in aisles,
                    occupied=occ,
                    heat=1.0 if occ else (0.15 if c in aisles else 0.0),
                    pair_id=pair_cells.get((r, c)),
                )
            )
    return SeatMapOut(
        showtime_id=showtime_id,
        hall_name=hall.name,
        rows=hall.rows,
        cols=hall.cols,
        cells=cells,
    )


@api_router.get("/holds", response_model=list[HoldOut])
def list_holds(db: Session = Depends(get_db)):
    return db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


def _log_conflict(db: Session, showtime_id: int, party_size: int, kind: str, reason: str) -> None:
    db.add(ConflictLog(showtime_id=showtime_id, party_size=party_size, kind=kind, reason=reason))
    db.commit()


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    pairs = db.scalars(select(CouplePair).where(CouplePair.hall_id == hall.id)).all()
    units = _pair_units(pairs)
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    result = BondResult()
    if body.preferred_row:
        result = find_bond_block(
            seats_by_row.get(body.preferred_row, []),
            holds,
            body.preferred_row,
            body.party_size,
            units,
        )
    if result.span is None:
        fallback = search_bond(seats_by_row, holds, body.party_size, units)
        # keep the more specific half-pair cause if either search saw one
        if fallback.span is not None or result.failure != BondFailure.HALF_PAIR:
            result = fallback
    block = result.span
    if block is None:
        if result.failure == BondFailure.HALF_PAIR and result.cuts:
            cut_row, cut_col = result.cuts[0]
            reason = (
                f"情侣对需整对落座：人数 {body.party_size} 在第{cut_row}排"
                f"只剩半对可用（{cut_col}-{cut_col + 1}列）"
            )
            _log_conflict(db, body.showtime_id, body.party_size, BondFailure.HALF_PAIR.value, reason)
            raise HTTPException(409, "情侣对不可拆：只剩半对可落座")
        _log_conflict(
            db,
            body.showtime_id,
            body.party_size,
            BondFailure.NO_CONTIGUOUS.value,
            f"无足够连续空座（人数 {body.party_size}）",
        )
        raise HTTPException(409, "无足够连续空座")

    hits = conflicts_with(holds, block)
    if hits:
        _log_conflict(
            db,
            body.showtime_id,
            body.party_size,
            "overlap",
            f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
        )
        raise HTTPException(409, "与既有持座冲突")

    couple_cols = sorted(
        p.start_col
        for p in pairs
        if p.row == block.row and block.start_col <= p.start_col and p.end_col <= block.end_col
    )
    code = f"SB-{int(datetime.utcnow().timestamp()) % 100000:05d}"
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=body.party_size,
        couple_cols=",".join(str(c) for c in couple_cols),
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
