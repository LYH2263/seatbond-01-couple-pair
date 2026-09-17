from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ConflictLog, CouplePair, Hall, SeatHold, Showtime


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Hall.id).limit(1)):
        return
    h1 = Hall(name="一号厅", rows=8, cols=12, aisle_cols="5,6")
    h2 = Hall(name="二号厅", rows=6, cols=10, aisle_cols="4,5")
    # 情侣厅：单排 9 座，中间一对情侣位（5-6 列），左右各有若干空座
    h3 = Hall(name="情侣厅", rows=1, cols=9, aisle_cols="")
    db.add_all([h1, h2, h3])
    db.flush()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=h1.id, film_title="星际旅人", start_at=now + timedelta(hours=2))
    s2 = Showtime(hall_id=h1.id, film_title="雾都夜曲", start_at=now + timedelta(hours=5))
    s3 = Showtime(hall_id=h2.id, film_title="山海经异", start_at=now + timedelta(hours=3))
    # 半对练习场：遗留单座持票占住情侣对右半格，人数 5 会逼出「只够半对」失败
    s4 = Showtime(hall_id=h3.id, film_title="半对练习场", start_at=now + timedelta(hours=4))
    # 整对练习场：情侣对整对空闲，人数 5 会整对纳入（2-6 列）
    s5 = Showtime(hall_id=h3.id, film_title="整对练习场", start_at=now + timedelta(hours=6))
    db.add_all([s1, s2, s3, s4, s5])
    db.flush()
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="SB-1001", row=3, start_col=2, end_col=4, party_size=3),
            SeatHold(showtime_id=s1.id, order_code="SB-1002", row=5, start_col=7, end_col=9, party_size=3),
            SeatHold(showtime_id=s3.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
            # 情侣对登记前的历史遗留单座持票，占住第 6 列（情侣对右半格）
            SeatHold(showtime_id=s4.id, order_code="SB-1004", row=1, start_col=6, end_col=6, party_size=1),
        ]
    )
    db.add(CouplePair(hall_id=h3.id, row=1, left_col=5, label="情侣座"))
    db.add(ConflictLog(showtime_id=s1.id, party_size=4, reason="与既有持座重叠：第3排 2-4"))
    db.commit()
