# paws3/core/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import pathlib
import yaml

# ---------- leaf configs ----------
@dataclass
class HorizonConfig:
    period_length: int = 10
    horizon_periods: int = 10
    replanning_step: int = 1
    start_period: int = 0
    end_period: int = 24

@dataclass
class PrincipalPolicyConfig:
    name: str = "even_flow"
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentBehaviorConfig:
    name: str = "profit_max_flow_stub"
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BilevelConfig:
    enabled: bool = False
    reformulation: str = "decomposition"

@dataclass
class SolverConfig:
    driver: str = "appsi"
    time_limit: int = 30
    mip_gap: Optional[float] = None

@dataclass
class RunConfig:
    random_seed: int = 42
    log_level: str = "INFO"
    out_dir: str = "runs/minimal"

# ---------- helpers ----------
def _as(cls, obj, defaults: Optional[Dict[str, Any]] = None):
    """Coerce a possibly-dict `obj` into dataclass `cls` (overlaying defaults)."""
    if isinstance(obj, cls):
        return obj
    if isinstance(obj, dict):
        base = {} if defaults is None else dict(defaults)
        base.update(obj)
        return cls(**base)  # type: ignore[arg-type]
    # nothing provided: build from defaults or empty
    return cls(**({} if defaults is None else defaults))  # type: ignore[arg-type]

# ---------- top-level ----------
@dataclass
class PawsConfig:
    horizon: HorizonConfig = field(default_factory=HorizonConfig)
    principal_policy: PrincipalPolicyConfig = field(default_factory=PrincipalPolicyConfig)
    agent_behavior: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    bilevel: BilevelConfig = field(default_factory=BilevelConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    run: RunConfig = field(default_factory=RunConfig)
    data_path: str = "examples/minimal/data"

    def __post_init__(self):
        # Coerce any stray dicts into the right dataclasses
        self.horizon = _as(HorizonConfig, self.horizon, HorizonConfig().__dict__)
        self.principal_policy = _as(PrincipalPolicyConfig, self.principal_policy, PrincipalPolicyConfig().__dict__)
        self.agent_behavior = _as(AgentBehaviorConfig, self.agent_behavior, AgentBehaviorConfig().__dict__)
        self.bilevel = _as(BilevelConfig, self.bilevel, BilevelConfig().__dict__)
        self.solver = _as(SolverConfig, self.solver, SolverConfig().__dict__)
        self.run = _as(RunConfig, self.run, RunConfig().__dict__)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PawsConfig":
        d = d or {}
        return cls(
            horizon=_as(HorizonConfig, d.get("horizon"), HorizonConfig().__dict__),
            principal_policy=_as(PrincipalPolicyConfig, d.get("principal_policy"), PrincipalPolicyConfig().__dict__),
            agent_behavior=_as(AgentBehaviorConfig, d.get("agent_behavior"), AgentBehaviorConfig().__dict__),
            bilevel=_as(BilevelConfig, d.get("bilevel"), BilevelConfig().__dict__),
            solver=_as(SolverConfig, d.get("solver"), SolverConfig().__dict__),
            run=_as(RunConfig, d.get("run"), RunConfig().__dict__),
            data_path=d.get("data_path", "examples/minimal/data"),
        )

def load_config(path_or_dict: str | Dict[str, Any] | PawsConfig) -> PawsConfig:
    """Accept YAML path, dict, or PawsConfig; always return a fully-typed PawsConfig."""
    if isinstance(path_or_dict, PawsConfig):
        # Ensure nested parts are coerced if someone built it with dicts
        return PawsConfig.from_dict(path_or_dict.__dict__)
    if isinstance(path_or_dict, dict):
        return PawsConfig.from_dict(path_or_dict)
    path = pathlib.Path(path_or_dict)
    with path.open("r") as f:
        d = yaml.safe_load(f) or {}
    return PawsConfig.from_dict(d)