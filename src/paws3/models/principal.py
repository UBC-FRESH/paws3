
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import pyomo.environ as pyo
from ..core.config import PawsConfig
from ..core.datatypes import ProblemData

from dataclasses import dataclass
from loguru import logger

from .types import PrincipalResult

# @dataclass
# class PrincipalResult:
#     model: pyo.ConcreteModel
#     solver_status: str
#     solver_driver: str
#     obj_value: float | None

_CANDIDATE_UL_VARS = ("commit", "flow", "ship", "deliveries", "harvest", "x")

def _extract_first_period_commitments_from_model(m, data, t0: int) -> Dict[Tuple[str, str], float]:
    # find a likely UL decision variable
    var = next((getattr(m, n) for n in _CANDIDATE_UL_VARS
                if hasattr(m, n) and isinstance(getattr(m, n), pyo.Var)), None)
    if var is None:
        logger.warning("No recognized UL decision variable found; returning empty commitments.")
        return {}

    # single default product if your UL is (stratum, t) rather than (stratum, product, t)
    default_product = "sawlog"
    if hasattr(data, "products") and data.products:
        default_product = next(iter(data.products))

    commits: Dict[Tuple[str, str], float] = {}
    for key in var:
        # key may be (s,p,t) or (s,t)
        try:
            s, p, tt = key
        except ValueError:
            # assume (s,t)
            s, tt = key
            p = default_product
        if tt != t0:
            continue
        v = float(var[key].value or 0.0)
        if v > 1e-9:
            commits[(s, p)] = commits.get((s, p), 0.0) + v
    return commits


def build_principal_model(data: ProblemData, cfg: PawsConfig, t0: int, T: int) -> PrincipalResult:
    m = pyo.ConcreteModel(name="principal_upper_level")
    m.T = periods = range(t0, t0 + T)
    m.S = strata = list(data.strata.keys())

    # # Decision: harvest area of stratum s in period t
    # m.X = pyo.Var(strata, periods, domain=pyo.NonNegativeReals)

    # X[s,t] = harvested area (ha) in stratum s at period t
    m.X = pyo.Var(m.S, m.T, domain=pyo.NonNegativeReals)

    # NEW: area conservation — cannot harvest more than the stand’s area across all periods in the window
    def _area_cap(m, s):
        return sum(m.X[s, t] for t in m.T) <= data.strata[s].area
    m.AreaCap = pyo.Constraint(m.S, rule=_area_cap)

    # Simple mass-balance (stub): volume_t = sum_s X[s,t] * yield[s,t]
    def vol_t(model, t):
        return sum(model.X[s, t] * data.yields.get((s, t), 0.0) for s in strata)
    m.vol = pyo.Expression(periods, rule=vol_t)

    # # Objective: placeholder even-flow (minimize squared deviation from average of first window)
    # avg = (1.0 / T) * sum(m.vol[t] for t in periods)
    # m.obj = pyo.Objective(expr=sum((m.vol[t] - avg) ** 2 for t in periods), sense=pyo.minimize)

    # LP even-flow via L1 deviations: minimize sum |vol[t] - z|
    m.z = pyo.Var(domain=pyo.Reals)  # target flow
    m.dpos = pyo.Var(periods, domain=pyo.NonNegativeReals)
    m.dneg = pyo.Var(periods, domain=pyo.NonNegativeReals)
    # tie deviations: vol[t] - z = dpos - dneg
    def dev_rule(model, t):
        return m.vol[t] - m.z == m.dpos[t] - m.dneg[t]
    m.dev = pyo.Constraint(periods, rule=dev_rule)
    # optional: set z to the mean with a linear constraint if you want:
    # m.mean_def = pyo.Constraint(expr = T * m.z == sum(m.vol[t] for t in periods))
    
    # Objective: minimize total deviation from z (robust L1)
    m.obj = pyo.Objective(expr=sum(m.dpos[t] + m.dneg[t] for t in periods), sense=pyo.minimize)
    
    # # Replace revenue-maximizing objective with this:
    # m.obj = pyo.Objective(expr=sum(m.X[s, t] for s in m.S for t in m.T), sense=pyo.minimize)

    # Example demand constraint (if provided)
    m.demand_lo = pyo.ConstraintList()
    m.demand_hi = pyo.ConstraintList()
    for d in data.demand:
        if d.period in periods:
            m.demand_lo.add(m.vol[d.period] >= d.min_vol)
            m.demand_hi.add(m.vol[d.period] <= d.max_vol)

    min_vol = float(cfg.principal_policy.params.get("min_vol", 0.0))

    # after you create m.vol[t], add a floor constraint per period in the window:
    def floor_rule(model, t):
        return model.vol[t] >= min_vol
    m.floor = pyo.Constraint(periods, rule=floor_rule)

    if cfg.principal_policy.name == "even_flow":
        vmin = float(cfg.principal_policy.params.get("min_vol", 0.0))
        # enforce only at the first step of the window
        m.MinFirstStep = pyo.Constraint(
            expr=sum(m.X[s, t0] * data.yields.get((s, t0), 0.0) * data.strata[s].area
                    for s in strata) >= vmin
        )
        # (Remove/skip the loop that enforced it for all t in [t0, t0+T-1])

    # still inside build_principal_model(...) before solve
    if cfg.principal_policy.name == "even_flow":
        Tset = range(t0, t0 + T)
        # upper bound if each stratum can be harvested at most once in the window
        ub_stock = sum(max(data.yields.get((s, t), 0.0) for t in Tset) * data.strata[s].area
                    for s in data.strata)
        req = float(cfg.principal_policy.params.get("min_vol", 0.0)) * T
        if req > ub_stock + 1e-6:
            logger.warning(
                "even_flow infeasible on window: need %.1f m3 (=%.1f×%d) but stock ≤ %.1f m3. "
                "Lower principal_policy.params.min_vol to ≤ %.1f, shorten the horizon, "
                "or enforce only at the first step.",
                req, cfg.principal_policy.params["min_vol"], T, ub_stock, ub_stock / T
            )

    # Solve (HiGHS via appsi if available, else exec)
    from .solvers import solve_model
    res = solve_model(m, cfg.solver)
    first_period_commitments = _extract_first_period_commitments_from_model(m, data, t0)

    from pyomo.environ import value, Objective

    # Safely get the active objective and evaluate it
    _obj = next(m.component_objects(Objective, active=True), None)
    objective_value = float(value(_obj.expr)) if _obj is not None else None

    return PrincipalResult(
        model=m,
        solver_status=res.get("status", "unknown"),
        t0=t0,
        T=T,
        objective_value=objective_value,
        # objective_value=getattr(m, "obj", None) and float(m.obj()),
        first_period_commitments=first_period_commitments,
    )
    # res = solve_model(m, cfg.solver)
    # return PrincipalResult(
    #     model=m,
    #     solver_status=res.get("status", "unknown"),
    #     solver_driver=res.get("driver", "unknown"),
    #     obj_value=pyo.value(m.obj),
    # )
