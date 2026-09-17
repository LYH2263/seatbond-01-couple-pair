from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ConflictLog, CouplePair, Hall, SeatHold, Showtime


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Hall.id).limit(1)):
        return
    h1 = Hall(name="一号厅", rows=8, cols=12, aisle_cols="5,6")
    h2 = Hall(name="二号厅", rows=6, cols=10, aisle_cols="4,5")
    # 情侣厅：单排 6 座无过道，中央一对情侣位（3-4），左右各有空座 1-2 / 5-6。
    # 人数 3 落窗 1-3 会切开该对 → 半对失败；人数 4 落窗 1-4 整对纳入 → 成功。
    h3 = Hall(name="情侣厅", rows=1, cols=6, aisle_cols="")
    db.add_all([h1, h2, h3])
    db.flush()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=h1.id, film_title="星际旅人", start_at=now + timedelta(hours=2))
    s2 = Showtime(hall_id=h1.id, film_title="雾都夜曲", start_at=now + timedelta(hours=5))
    s3 = Showtime(hall_id=h2.id, film_title="山海经异", start_at=now + timedelta(hours=3))
    s4 = Showtime(hall_id=h3.id, film_title="恋恋笔记本", start_at=now + timedelta(hours=4))
    db.add_all([s1, s2, s3, s4])
    db.flush()
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="SB-1001", row=3, start_col=2, end_col=4, party_size=3),
            SeatHold(showtime_id=s1.id, order_code="SB-1002", row=5, start_col=7, end_col=9, party_size=3),
            SeatHold(showtime_id=s3.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
        ]
    )
    # 一号厅第6排 9-10 列也登记一对（7-12 段中央），SB-1004 示范整对纳入的持座单。
    db.add(CouplePair(hall_id=h1.id, row=6, start_col=9))
    db.add(
        SeatHold(
            showtime_id=s2.id,
            order_code="SB-1004",
            row=6,
            start_col=7,
            end_col=10,
            party_size=4,
            couple_cols="9",
        )
    )
    # 情侣厅的情侣对（第1排 3-4 列）。
    db.add(CouplePair(hall_id=h3.id, row=1, start_col=3))
    db.add(
        ConflictLog(
            showtime_id=s1.id, party_size=4, kind="overlap", reason="与既有持座重叠：第3排 2-4"
        )
    )
    db.add(
        ConflictLog(
            showtime_id=s4.id,
            party_size=3,
            kind="half_pair",
            reason="情侣对需整对落座：人数 3 在第1排只剩半对可用（3-4列）",
        )
    )
    db.commit()
