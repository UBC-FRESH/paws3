
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

#_CANDIDATE_UL_VARS = ("commit", "flow", "ship", "deliveries", "harvest", "x")
_CANDIDATE_UL_VARS = ("commit", "flow", "ship", "deliveries", "harvest", "x", "X", "H", "harvest_area", "Sell", "sell")

def _extract_first_period_commitments_from_model(m, data, t0: int) -> dict[tuple[str,str], float]:
    # Try typical cut variables with (stratum, t) indexing
    for cand in ("cut", "x", "harvest", "h", "c"):
        if hasattr(m, cand):
            var = getattr(m, cand)
            # Expect (s, t) indexing
            try:
                idx = var.index_set()
            except Exception:
                idx = None
            if idx is not None:
                out = {}
                for s in data.strata:
                    key = (s, t0)
                    if key in idx:
                        v = pyo.value(var[key])
                        if abs(v) > 1e-9:
                            # v is a fraction or a direct volume; pick the right transform
                            # If v is a fraction of area harvested:
                            vol = v * data.yields.get((s, t0), 0.0) * data.strata[s].area
                            out[(s, "sawlog")] = vol
                if out:
                    return out
    # Fallback: if only an aggregate vol[t] exists, return one pooled “ALL” entry
    if hasattr(m, "vol") and (t0 in m.vol):
        vt = float(pyo.value(m.vol[t0]))
        if vt > 1e-9:
            return {("ALL", "sawlog"): vt}
    return {}

# def _extract_first_period_commitments_from_model(m, data, t0: int) -> Dict[Tuple[str, str], float]:
#     # find a likely UL decision variable
#     var = next((getattr(m, n) for n in _CANDIDATE_UL_VARS
#                 if hasattr(m, n) and isinstance(getattr(m, n), pyo.Var)), None)
#     if var is None:
#         logger.warning("No recognized UL decision variable found; returning empty commitments.")
#         return {}

#     # single default product if your UL is (stratum, t) rather than (stratum, product, t)
#     default_product = "sawlog"
#     if hasattr(data, "products") and data.products:
#         default_product = next(iter(data.products))

#     commits: Dict[Tuple[str, str], float] = {}
#     for key in var:
#         # key may be (s,p,t) or (s,t)
#         try:
#             s, p, tt = key
#         except ValueError:
#             # assume (s,t)
#             s, tt = key
#             p = default_product
#         if tt != t0:
#             continue
#         v = float(var[key].value or 0.0)
#         if v > 1e-9:
#             commits[(s, p)] = commits.get((s, p), 0.0) + v
#     return commits


# 
from typing import Dict, Tuple
import pyomo.environ as pyo
from loguru import logger

# correct imports
from ..core.datatypes import ProblemData
from .types import PrincipalResult, AgentResponse
from ..core.config import load_config, PawsConfig

def build_principal_model(data: ProblemData, cfg: PawsConfig, t0: int, T: int) -> PrincipalResult:
    """
    Principal (UL) model over a T-period long-term window starting at absolute period t0.

    - Decision: X[s,t] = harvested area (ha) in stratum s at absolute period t.
    - Volume (m3) in period t: vol[t] = sum_s X[s,t] * yield[(s, t_rel)], where t_rel = t - t0 in [0..T-1].
      (Assumes yields are m3/ha per LT period, and CSV provided exactly T rows per stand.)
    - Area conservation: sum_t X[s,t] <= area[s].
    - Physical cap: vol[t] <= sum_s area[s] * yield[(s, t_rel)]  (safety; redundant with area conservation but useful).
    - Even-flow policy: enforce only first-step minimum m.vol[t0] >= min_vol.
    - Objective: maximize total delivered volume over the window (simple & robust).
    """
    m = pyo.ConcreteModel(name="principal_upper_level")

    # Index sets
    m.S = pyo.Set(initialize=list(data.strata.keys()))
    m.T = pyo.Set(initialize=list(range(t0, t0 + T)))

    # Helper: long-term yield lookup using window-relative index
    def yld(s: str, t_abs: int) -> float:
        t_rel = t_abs - t0
        return float(data.yields.get((s, t_rel), 0.0))

    # ---------- Decisions ----------
    # X[s,t] = harvested area (ha)
    m.X = pyo.Var(m.S, m.T, domain=pyo.NonNegativeReals)

    # ---------- Constraints ----------
    # Area conservation per stratum
    def _area_cap(_m, s):
        return sum(_m.X[s, t] for t in _m.T) <= data.strata[s].area
    m.AreaCap = pyo.Constraint(m.S, rule=_area_cap)

    # Period volume expression (m3)
    def _vol_rule(_m, t):
        return sum(_m.X[s, t] * yld(s, t) for s in _m.S)
    m.vol = pyo.Expression(m.T, rule=_vol_rule)

    # Physical cap per period (safety)
    cap = {t: sum(data.strata[s].area * yld(s, t) for s in m.S) for t in m.T}
    def _cap_con(_m, t):
        return _m.vol[t] <= cap[t] + 1e-9
    m.Cap = pyo.Constraint(m.T, rule=_cap_con)

    # Demand constraints (if any fall inside this absolute window)
    m.DemandLo = pyo.ConstraintList()
    m.DemandHi = pyo.ConstraintList()
    for d in data.demand:
        if d.period in m.T:
            m.DemandLo.add(m.vol[d.period] >= d.min_vol)
            m.DemandHi.add(m.vol[d.period] <= d.max_vol)

    # Even-flow minimum on the first step only
    if cfg.principal_policy.name == "even_flow":
        min_vol = float(cfg.principal_policy.params.get("min_vol", 0.0))
        # Only enforce where the physical cap is positive
        if cap[t0] > 1e-6 and min_vol > 0.0:
            m.MinFirst = pyo.Constraint(expr=m.vol[t0] >= min_vol)

        # Feasibility heads-up (optional)
        total_stock = sum(max(float(data.yields.get((s, k), 0.0)) for k in range(T)) * data.strata[s].area
                          for s in data.strata)
        if min_vol * T > total_stock + 1e-6:
            logger.warning(
                "even_flow may be infeasible on window starting t0=%d: need %.1f (=%.1f×%d) vs stock ≤ %.1f m3. "
                "Lower min_vol, shorten T, or enforce only at first step.",
                t0, min_vol * T, min_vol, T, total_stock
            )

    # ---------- Objective ----------
    # Basic objective: maximize total volume over the window
    m.obj = pyo.Objective(expr=sum(m.vol[t] for t in m.T), sense=pyo.maximize)

    # ---------- Solve ----------
    from .solvers import solve_model
    res = solve_model(m, cfg.solver)

    # ---------- Build first-period commitments (UL -> LL) ----------
    # Commit per-stratum volume at the first step of this window (t = t0).
    def _first_period_commitments() -> Dict[Tuple[str, str], float]:
        out: Dict[Tuple[str, str], float] = {}
        if t0 not in m.T:
            return out
        for s in m.S:
            x_ha = pyo.value(m.X[s, t0]) if (s, t0) in m.X else 0.0
            if x_ha and x_ha > 1e-9:
                vol_m3 = x_ha * yld(s, t0)  # m3/ha * ha = m3
                if vol_m3 > 1e-6:
                    out[(s, "sawlog")] = out.get((s, "sawlog"), 0.0) + float(vol_m3)
        # Fallback: if per-stratum is empty but aggregate > 0, send pooled
        if not out:
            v0 = float(pyo.value(m.vol[t0]))
            if v0 > 1e-6:
                out[("ALL", "sawlog")] = v0
        return out

    first_period_commitments = _first_period_commitments()

    # Safe objective value extraction
    _obj_val = None
    try:
        _obj_val = float(pyo.value(m.obj))
    except Exception:
        pass

    # Useful debug
    logger.debug("UL cap[t0]=%.1f m3, vol[t0]=%.1f m3, commitments=%d entries",
                 cap.get(t0, 0.0), float(pyo.value(m.vol[t0])) if t0 in m.T else 0.0,
                 len(first_period_commitments))

    return PrincipalResult(
        model=m,
        solver_status=res.get("status", "unknown"),
        t0=t0,
        T=T,
        objective_value=_obj_val,
        first_period_commitments=first_period_commitments,
    )