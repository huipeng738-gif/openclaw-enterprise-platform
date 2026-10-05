"""Validated payload for user and OpenClaw metric queries."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MetricQuery(BaseModel):
    metric: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    group_by: Literal['day', 'week', 'month'] = 'day'
