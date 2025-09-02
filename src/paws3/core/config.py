
from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import Literal, Optional, List, Dict

class HorizonConfig(BaseModel):
    period_length: int = Field(7, description="Days per planning period")
    horizon_periods: int = Field(12, description="Number of periods in the optimization window")
    replanning_step: int = Field(1, description="Advance this many periods between replans")
    start_period: int = 0
    end_period: int = 52

class PrincipalPolicyConfig(BaseModel):
    name: str = "even_flow"
    params: Dict[str, float] = Field(default_factory=dict)

class AgentBehaviorConfig(BaseModel):
    name: str = "profit_max_flow_stub"
    params: Dict[str, float] = Field(default_factory=dict)

class BilevelConfig(BaseModel):
    enabled: bool = False
    reformulation: Literal["kkt", "bigm", "decomposition"] = "decomposition"

class SolverConfig(BaseModel):
    driver: Literal["appsi", "exec", "auto"] = "auto"
    time_limit: int = 120
    mip_gap: Optional[float] = None

class RunConfig(BaseModel):
    random_seed: int = 42
    log_level: Literal["DEBUG", "INFO", "WARNING"] = "INFO"
    out_dir: str = "runs/default"

class PawsConfig(BaseModel):
    horizon: HorizonConfig = HorizonConfig()
    principal_policy: PrincipalPolicyConfig = PrincipalPolicyConfig()
    agent_behavior: AgentBehaviorConfig = AgentBehaviorConfig()
    bilevel: BilevelConfig = BilevelConfig()
    solver: SolverConfig = SolverConfig()
    run: RunConfig = RunConfig()
    data_path: str = "examples/data/minimal"
