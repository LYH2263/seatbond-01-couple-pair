from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    aisle_cols: Mapped[str] = mapped_column(String(80), default="")  # comma-separated
    showtimes: Mapped[list["Showtime"]] = relationship(back_populates="hall")
    couple_pairs: Mapped[list["CouplePair"]] = relationship(back_populates="hall")


class CouplePair(Base):
    """情侣对：同排相邻两列绑定，锁座必须整对写入或整对跳过。"""

    __tablename__ = "couple_pairs"
    __table_args__ = (
        UniqueConstraint("hall_id", "row", "start_col", name="uq_couple_pair_cell"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    row: Mapped[int] = mapped_column(Integer)
    start_col: Mapped[int] = mapped_column(Integer)  # pair = start_col, start_col + 1
    hall: Mapped[Hall] = relationship(back_populates="couple_pairs")

    @property
    def end_col(self) -> int:
        return self.start_col + 1


class Showtime(Base):
    __tablename__ = "showtimes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    film_title: Mapped[str] = mapped_column(String(120))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    hall: Mapped[Hall] = relationship(back_populates="showtimes")
    holds: Mapped[list["SeatHold"]] = relationship(back_populates="showtime")


class SeatHold(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (UniqueConstraint("showtime_id", "row", "start_col", "end_col", name="uq_hold_span"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"))
    order_code: Mapped[str] = mapped_column(String(40))
    row: Mapped[int] = mapped_column(Integer)
    start_col: Mapped[int] = mapped_column(Integer)
    end_col: Mapped[int] = mapped_column(Integer)
    party_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="held")
    # comma-separated couple-pair start cols included in this hold, "" = none
    couple_cols: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    showtime: Mapped[Showtime] = relationship(back_populates="holds")


class ConflictLog(Base):
    __tablename__ = "conflict_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"))
    party_size: Mapped[int] = mapped_column(Integer)
    # machine-distinguishable cause: no_contiguous | half_pair | overlap
    kind: Mapped[str] = mapped_column(String(20), default="")
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
