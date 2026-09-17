from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class HallOut(BaseModel):
    id: int
    name: str
    rows: int
    cols: int
    aisle_cols: list[int]
    model_config = {"from_attributes": True}


class CouplePairOut(BaseModel):
    id: int
    hall_id: int
    row: int
    start_col: int
    end_col: int
    model_config = {"from_attributes": True}


class CouplePairRequest(BaseModel):
    row: int = Field(ge=1)
    start_col: int = Field(ge=1)


class ShowtimeOut(BaseModel):
    id: int
    hall_id: int
    film_title: str
    start_at: datetime
    hall_name: str | None = None
    model_config = {"from_attributes": True}


class HoldOut(BaseModel):
    id: int
    showtime_id: int
    order_code: str
    row: int
    start_col: int
    end_col: int
    party_size: int
    status: str
    couple_cols: list[int] = []  # start cols of couple pairs included in this hold
    model_config = {"from_attributes": True}

    @field_validator("couple_cols", mode="before")
    @classmethod
    def _split_couple_cols(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v or []


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None


class ConflictOut(BaseModel):
    id: int
    showtime_id: int
    party_size: int
    kind: str
    reason: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SeatMapCell(BaseModel):
    row: int
    col: int
    is_aisle: bool
    occupied: bool
    heat: float
    pair_id: int | None = None  # set when the cell belongs to a couple pair


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    cells: list[SeatMapCell]
