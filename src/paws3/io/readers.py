
from __future__ import annotations
import random
from ..core.datatypes import ProblemData, ForestStratum, PeriodDemand

def synthesize_problem_data() -> ProblemData:
    random.seed(0)
    strata = {
        f"S{i}": ForestStratum(id=f"S{i}", area=100 + 10*i, species="PINE", age=60 + 3*i)
        for i in range(5)
    }
    yields = {}
    for s in strata:
        for t in range(0, 52):
            yields[(s, t)] = 2.0 + (hash(s) % 3) * 0.1
    demand = [PeriodDemand(period=t, species="PINE", min_vol=0.0, max_vol=1e6) for t in range(0,52)]
    prices = {"PINE": 100.0}
    costs = {"harvest": 50.0}
    return ProblemData(strata=strata, yields=yields, demand=demand, prices=prices, costs=costs)
