
from __future__ import annotations
import pyomo.environ as pyo
from ..core.config import SolverConfig
from loguru import logger

def solve_model(m: pyo.ConcreteModel, cfg: SolverConfig) -> dict:
    driver = cfg.driver
    if driver == "auto":
        try:
            from appsi.solvers.highs import Highs
            solver = Highs()
            logger.debug("Using appsi.highs")
            res = solver.solve(m, time_limit=cfg.time_limit, gap_rel=cfg.mip_gap)
            return {"status": str(res.solver.termination_condition)}
        except Exception as e:
            logger.warning("Falling back to exec HiGHS: {}", e)
            driver = "exec"
    if driver == "appsi":
        from appsi.solvers.highs import Highs
        solver = Highs()
        res = solver.solve(m, time_limit=cfg.time_limit, gap_rel=cfg.mip_gap)
        return {"status": str(res.solver.termination_condition)}
    elif driver == "exec":
        solver = pyo.SolverFactory("highs")
        res = solver.solve(m, tee=False, timelimit=cfg.time_limit)
        return {"status": str(res.solver.termination_condition)}
    else:
        raise ValueError(f"Unknown solver driver: {driver}")
