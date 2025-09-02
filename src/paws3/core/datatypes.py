
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple

class ForestStratum(BaseModel):
    id: str
    area: float
    species: str
    age: int

class PeriodDemand(BaseModel):
    period: int
    species: str
    min_vol: float = 0.0
    max_vol: float = 1e12

class ProblemData(BaseModel):
    strata: Dict[str, ForestStratum] = Field(default_factory=dict)
    yields: Dict[Tuple[str,int], float] = Field(default_factory=dict)  # (stratum, period)->yield m3/ha
    demand: List[PeriodDemand] = Field(default_factory=list)
    prices: Dict[str, float] = Field(default_factory=dict)
    costs: Dict[str, float] = Field(default_factory=dict)
