
from __future__ import annotations
import pyomo.environ as pyo
from ..core.config import SolverConfig
from loguru import logger

def _termcond(res):
    tc = getattr(getattr(res, "solver", None), "termination_condition", None)
    return tc if tc is not None else getattr(res, "termination_condition", None)

def solve_model(m: pyo.ConcreteModel, cfg: SolverConfig) -> dict:
    driver = cfg.driver
    if driver in ("auto", "appsi"):
        try:
            from pyomo.contrib.appsi.solvers.highs import Highs
            solver = Highs()
            solver.config.time_limit = cfg.time_limit
            if cfg.mip_gap is not None:
                solver.config.mip_gap = cfg.mip_gap
            res = solver.solve(m)
            return {"status": str(_termcond(res)), "driver": "appsi"}
        except Exception as e:
            logger.warning("Falling back to exec HiGHS: {}", e)
    # exec path
    solver = pyo.SolverFactory("highs")
    if cfg.time_limit is not None:
        solver.options["time_limit"] = cfg.time_limit
    if cfg.mip_gap is not None:
        solver.options["mip_rel_gap"] = cfg.mip_gap
    res = solver.solve(m, tee=False)
    return {"status": str(_termcond(res)), "driver": "exec"}

# def _termcond(res):
#     # Works for both APPSI HighsResults (res.termination_condition)
#     # and classic Pyomo Results (res.solver.termination_condition)
#     tc = getattr(getattr(res, "solver", None), "termination_condition", None)
#     if tc is None:
#         tc = getattr(res, "termination_condition", None)
#     return tc

# def solve_model(m: pyo.ConcreteModel, cfg: SolverConfig) -> dict:
#     driver = cfg.driver
#     if driver in ("auto", "appsi"):
#         try:
#             from pyomo.contrib.appsi.solvers.highs import Highs
#             solver = Highs()
#             solver.config.time_limit = cfg.time_limit
#             if cfg.mip_gap is not None:
#                 solver.config.mip_gap = cfg.mip_gap
#             res = solver.solve(m)
#             return {"status": str(_termcond(res)), "driver": "appsi"}
#         except Exception as e:
#             logger.warning("Falling back to exec HiGHS: {}", e)

#     # exec path
#     solver = pyo.SolverFactory("highs")
#     if cfg.time_limit is not None:
#         solver.options["time_limit"] = cfg.time_limit
#     if cfg.mip_gap is not None:
#         solver.options["mip_rel_gap"] = cfg.mip_gap
#     res = solver.solve(m, tee=False)
#     return {"status": str(_termcond(res)), "driver": "exec"}

