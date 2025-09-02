
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from loguru import logger
from .config import PawsConfig
from ..models.principal import build_principal_model, PrincipalResult
from ..models.agent import emulate_agent_behavior
from ..core.interfaces import AgentRequest
from ..plugins.registry import get as get_plugin
from ..models.bilevel import solve_bilevel_if_enabled
from ..io.loaders import load_problem_data

@dataclass
class SimState:
    t0: int
    t_end: int
    t: int
    cum_stats: Dict[str, Any]

class RollingHorizonSimulator:
    def __init__(self, cfg: PawsConfig):
        self.cfg = cfg
        self.data = load_problem_data(cfg.data_path)

    def run(self) -> Dict[str, Any]:
        h = self.cfg.horizon
        state = SimState(t0=h.start_period, t_end=h.end_period, t=h.start_period, cum_stats={})
        logger.info("Starting rolling-horizon simulation at period {} -> {}", state.t, state.t_end)
        while state.t < state.t_end:
            logger.info("Replanning window t=[{}, {}]", state.t, state.t + h.horizon_periods - 1)
            # 1) build and solve principal model on current window
            pr = build_principal_model(self.data, self.cfg, t0=state.t, T=h.horizon_periods)
            # 2) emulate agent (or solve lower-level) on the first-step decision
            if self.cfg.principal_policy.name == 'ws3_emulator':
                # Build state for principal
                state_dict = {'period': state.t, 'inventory': {k: {'area': v.area, 'yield_p1': self.data.yields.get((k, state.t), 1.0)} for k,v in self.data.strata.items()}}
                ws3_fn = get_plugin('ws3_emulator')
                pdec = ws3_fn(state_dict, **self.cfg.principal_policy.params)
                # Map to an AgentRequest for FHOPS or other agents
                areq = AgentRequest(period=state.t, blocks=[{'stratum': s, 'product': p, 'ub_vol': vol} for (s,p), vol in pdec.commitments.items()], commitments=pdec.commitments)
                if self.cfg.agent_behavior.name == 'fhops_exec':
                    fhops_fn = get_plugin('fhops_exec')
                    _aresp = fhops_fn(areq, **self.cfg.agent_behavior.params)
                else:
                    emulate_agent_behavior(self.data, self.cfg, pr, current_period=state.t)
            else:
                emulate_agent_behavior(self.data, self.cfg, pr, current_period=state.t)
            # 3) (optional) bilevel solve/refinement
            solve_bilevel_if_enabled(self.data, self.cfg, pr, current_period=state.t)
            # 4) advance time
            state.t += h.replanning_step
        logger.success("Simulation complete.")
        return {"status": "ok"}
