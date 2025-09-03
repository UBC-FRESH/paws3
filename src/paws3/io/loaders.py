
from __future__ import annotations
import yaml, json
from pathlib import Path
from . import readers as rdrs
from ..core.config import PawsConfig
from ..core.datatypes import ProblemData

from loguru import logger
from .readers import synthesize_problem_data
from .csv_loader import load_problem_data_from_csvs 

import logging
logger = logging.getLogger(__name__)

def _expand_absolute_yields(data: ProblemData, end_period: int, horizon_periods: int, period_years: int) -> None:
    """
    Convert yields keyed by (stratum, age_bin) into absolute-time yields keyed by (stratum, t).
    Clips to the last available bin once the stand ages beyond the table.
    """
    # figure out the max bin for each stratum from what's in the CSV
    max_bin_by_s = {}
    for (s, age_bin), y in data.yields.items():
        max_bin_by_s[s] = max(age_bin, max_bin_by_s.get(s, 0))

    t_max = end_period + horizon_periods  # cover last rolling window
    expanded = {}
    for s, strat in data.strata.items():
        age0 = getattr(strat, "age0", 0)  # initial stand age in years
        max_bin = max_bin_by_s.get(s, 0)
        for t in range(0, t_max + 1):
            age_years = age0 + t * period_years
            age_bin = int(age_years // period_years)
            age_bin = min(age_bin, max_bin)  # clip to last bin
            expanded[(s, t)] = data.yields.get((s, age_bin), 0.0)

    data.yields = expanded  # overwrite with absolute-time map
    logger.info("Expanded yields to absolute time: now have entries for t∈[0..%d]", t_max)

def load_problem_data(cfg: PawsConfig) -> ProblemData:
    logger.info("Loading ProblemData from CSVs under %s", cfg.data_path)
    data = load_problem_data_from_csvs(cfg.data_path)

    # Make age-bin yields usable across the whole sim horizon
    _expand_absolute_yields(
        data,
        end_period=cfg.horizon.end_period,
        horizon_periods=cfg.horizon.horizon_periods,
        period_years=cfg.horizon.period_length or 10,
    )
    return data

# def load_problem_data(data_dir: str):
#     dp = Path(data_dir)
#     problem_json = dp / "problem.json"

#     if problem_json.exists():
#         logger.info("Loading ProblemData from {}", problem_json)
#         # TODO: JSON loader (not implemented yet)
#         return synthesize_problem_data()
#     else:
#         # NEW: if we see strata.csv + yields.csv, load from CSVs
#         if (dp / "strata.csv").exists() and (dp / "yields.csv").exists():
#             logger.info("Loading ProblemData from CSVs under {}", dp)
#             return load_problem_data_from_csvs(str(dp))

#         logger.warning("No problem.json (or CSVs) found in {}; synthesizing a demo dataset", dp)
#         return synthesize_problem_data()

def load_config(path: str | Path) -> PawsConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text())
    return PawsConfig(**data)

# def load_problem_data(data_path: str | Path) -> ProblemData:
#     dp = Path(data_path)
#     # Minimal placeholder: load from JSON if present; else synthesize tiny dataset
#     js = dp / "problem.json"
#     if js.exists():
#         return ProblemData(**json.loads(js.read_text()))
#     return rdrs.synthesize_problem_data()
