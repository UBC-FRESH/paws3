
from __future__ import annotations
from typing import Protocol, Dict, Any, List, Tuple
from pydantic import BaseModel

class PrincipalDecision(BaseModel):
    period: int
    # volume commitments by (stratum or block, product): m3
    commitments: Dict[Tuple[str, str], float] = {}

class AgentRequest(BaseModel):
    period: int
    # requested blocks with upper bounds on take, and metadata needed by FHOPS
    blocks: List[Dict[str, Any]] = []
    # optional: mill or product commitments to honour
    commitments: Dict[Tuple[str, str], float] = {}

class AgentResponse(BaseModel):
    period: int
    # realized production/flows/costs for first-period
    summary: Dict[str, Any]
    # realized block-level schedule (subset of blocks)
    schedule: List[Dict[str, Any]] = []

class PrincipalEmulator(Protocol):
    def plan_first_period(self, state: Dict[str, Any]) -> PrincipalDecision: ...

class OperationsAgent(Protocol):
    def schedule_first_period(self, req: AgentRequest) -> AgentResponse: ...
