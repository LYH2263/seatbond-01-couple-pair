from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ConflictLog, CouplePair, Hall, SeatHold, Showtime
from app.schemas.schemas import (
    ConflictOut,
    CouplePairOut,
    CouplePairUpsert,
    HallOut,
    HoldOut,
    HoldRequest,
    SeatMapCell,
    SeatMapOut,
    ShowtimeOut,
)
from app.services.bond_engine import (
    HALF_PAIR,
    CouplePairSpan,
    HoldSpan,
    SeatCell,
    conflicts_with,
    find_block_across_rows,
    find_block_in_row,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _hall_out(h: Hall) -> HallOut:
    return HallOut(id=h.id, name=h.name, rows=h.rows, cols=h.cols, aisle_cols=_aisles(h))


def _couple_cols(hold: SeatHold) -> list[int]:
    if not hold.couple_cols:
        return []
    return [int(x) for x in hold.couple_cols.split(",") if x.strip()]


def _hold_out(h: SeatHold) -> HoldOut:
    return HoldOut(
        id=h.id,
        showtime_id=h.showtime_id,
        order_code=h.order_code,
        row=h.row,
        start_col=h.start_col,
        end_col=h.end_col,
        party_size=h.party_size,
        status=h.status,
        couple_cols=_couple_cols(h),
    )


def _pair_spans(pairs: list[CouplePair]) -> list[CouplePairSpan]:
    return [CouplePairSpan(row=p.row, left_col=p.left_col) for p in pairs]


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    return [_hall_out(h) for h in db.scalars(select(Hall).order_by(Hall.id)).all()]


def _validate_pair(db: Session, hall: Hall, row: int, left_col: int, ignore_id: int | None = None):
    if not 1 <= row <= hall.rows:
        raise HTTPException(422, "排号超出影厅范围")
    if not 1 <= left_col or left_col + 1 > hall.cols:
        raise HTTPException(422, "列号超出影厅范围")
    aisles = set(_aisles(hall))
    if left_col in aisles or left_col + 1 in aisles:
        raise HTTPException(409, "情侣对不得跨过道列登记")
    existing = db.scalars(
        select(CouplePair).where(CouplePair.hall_id == hall.id, CouplePair.row == row)
    ).all()
    for p in existing:
        if ignore_id is not None and p.id == ignore_id:
            continue
        if abs(p.left_col - left_col) <= 1:  # spans {l, l+1} overlap
            raise HTTPException(409, f"与既有情侣对重叠：第{p.row}排 {p.left_col}-{p.right_col}")


@api_router.get("/halls/{hall_id}/pairs", response_model=list[CouplePairOut])
def list_pairs(hall_id: int, db: Session = Depends(get_db)):
    if not db.get(Hall, hall_id):
        raise HTTPException(404, "影厅不存在")
    return db.scalars(
        select(CouplePair)
        .where(CouplePair.hall_id == hall_id)
        .order_by(CouplePair.row, CouplePair.left_col)
    ).all()


@api_router.post("/halls/{hall_id}/pairs", response_model=CouplePairOut, status_code=201)
def create_pair(hall_id: int, body: CouplePairUpsert, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    _validate_pair(db, hall, body.row, body.left_col)
    pair = CouplePair(hall_id=hall.id, row=body.row, left_col=body.left_col, label=body.label)
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair


@api_router.put("/pairs/{pair_id}", response_model=CouplePairOut)
def update_pair(pair_id: int, body: CouplePairUpsert, db: Session = Depends(get_db)):
    pair = db.get(CouplePair, pair_id)
    if not pair:
        raise HTTPException(404, "情侣对不存在")
    hall = db.get(Hall, pair.hall_id)
    assert hall
    _validate_pair(db, hall, body.row, body.left_col, ignore_id=pair.id)
    pair.row = body.row
    pair.left_col = body.left_col
    pair.label = body.label
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
    pairs = db.scalars(select(CouplePair).where(CouplePair.hall_id == hall.id)).all()
    couple_cells: set[tuple[int, int]] = set()
    for p in pairs:
        couple_cells.add((p.row, p.left_col))
        couple_cells.add((p.row, p.right_col))
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
                    couple=(r, c) in couple_cells,
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
    rows = db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()
    return [_hold_out(h) for h in rows]


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    pairs = db.scalars(select(CouplePair).where(CouplePair.hall_id == hall.id)).all()
    pair_spans = _pair_spans(pairs)
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    block = None
    if body.preferred_row:
        block = find_block_in_row(
            seats_by_row.get(body.preferred_row, []),
            holds,
            pair_spans,
            body.preferred_row,
            body.party_size,
        ).block
    reason = None
    if block is None:
        res = find_block_across_rows(seats_by_row, holds, pair_spans, body.party_size)
        block, reason = res.block, res.reason
    if block is None:
        if reason == HALF_PAIR:
            log_reason = f"半对占用：情侣对仅剩单格，需整对纳入（人数 {body.party_size}）"
            detail = "半对占用：情侣对不可拆占"
        else:
            log_reason = f"无足够连续空座（人数 {body.party_size}）"
            detail = "无足够连续空座"
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=log_reason,
            )
        )
        db.commit()
        raise HTTPException(409, detail)

    hits = conflicts_with(holds, block)
    if hits:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
            )
        )
        db.commit()
        raise HTTPException(409, "与既有持座冲突")

    couple_cols = sorted(
        {
            c
            for p in pair_spans
            if p.row == block.row
            for c in (p.left_col, p.right_col)
            if block.start_col <= c <= block.end_col
        }
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
    return _hold_out(hold)
