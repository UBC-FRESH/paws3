# src/paws3/models/types.py
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

@dataclass
class AgentResponse:
    # keep it minimal; expand later if needed
    accepted: bool = True
    ll_objective: Optional[float] = None
    shipments: Dict[Tuple[str, str], float] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PrincipalResult:
    model: Any
    solver_status: str
    t0: int
    T: int
    objective_value: Optional[float] = None
    # NEW: (stratum, product) -> committed volume in the *first* period of the window
    first_period_commitments: Dict[Tuple[str, str], float] = field(default_factory=dict)