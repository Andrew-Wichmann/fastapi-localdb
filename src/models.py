from datetime import date

from pydantic import BaseModel


class Position(BaseModel):
    id: str
    quantity: float


class MarginRequest(BaseModel):
    cob_date: date
    positions: list[Position]


class MarginResponse(BaseModel):
    total_margin: float
    cob_date: date
