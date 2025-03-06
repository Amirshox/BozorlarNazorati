from typing import Optional

from pydantic import BaseModel


class CountBreakdownSchema(BaseModel):
    male: Optional[int] = 0
    female: Optional[int] = 0
    undefined: Optional[int] = 0


class VisitsBreakdownSchema(BaseModel):
    total: int
    trend: float
    gender: CountBreakdownSchema


class AgeGenderBreakdownSchema(BaseModel):
    age_group: str
    counts: CountBreakdownSchema


class HourlyBreakdownSchema(BaseModel):
    hour: int
    count: int


class DailyBreakdownSchema(BaseModel):
    date: int
    counts: CountBreakdownSchema
