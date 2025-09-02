
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import pyomo.environ as pyo
from ..core.config import PawsConfig
from ..core.datatypes import ProblemData

@dataclass
class PrincipalResult:
    model: pyo.ConcreteModel
    solver_status: str
    obj_value: float | None

def build_principal_model(data: ProblemData, cfg: PawsConfig, t0: int, T: int) -> PrincipalResult:
    m = pyo.ConcreteModel(name="principal_upper_level")
    periods = range(t0, t0 + T)
    strata = list(data.strata.keys())

    # Decision: harvest area of stratum s in period t
    m.X = pyo.Var(strata, periods, domain=pyo.NonNegativeReals)

    # Simple mass-balance (stub): volume_t = sum_s X[s,t] * yield[s,t]
    def vol_t(model, t):
        return sum(model.X[s, t] * data.yields.get((s, t), 0.0) for s in strata)
    m.vol = pyo.Expression(periods, rule=vol_t)

    # Objective: placeholder even-flow (minimize squared deviation from average of first window)
    avg = (1.0 / T) * sum(m.vol[t] for t in periods)
    m.obj = pyo.Objective(expr=sum((m.vol[t] - avg) ** 2 for t in periods), sense=pyo.minimize)

    # Example demand constraint (if provided)
    m.demand_lo = pyo.ConstraintList()
    m.demand_hi = pyo.ConstraintList()
    for d in data.demand:
        if d.period in periods:
            m.demand_lo.add(m.vol[d.period] >= d.min_vol)
            m.demand_hi.add(m.vol[d.period] <= d.max_vol)

    # Solve (HiGHS via appsi if available, else exec)
    from .solvers import solve_model
    res = solve_model(m, cfg.solver)
    return PrincipalResult(model=m, solver_status=res.get("status", "unknown"), obj_value=pyo.value(m.obj))
