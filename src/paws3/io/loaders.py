from __future__ import annotations

from pathlib import Path
import yaml
import logging
import re

from ..core.config import PawsConfig
from ..core.datatypes import ProblemData
from .csv_loader import load_problem_data_from_csvs

logger = logging.getLogger(__name__)


def _years(value) -> float:
    """Convert '10y', '6mo', '52w', '7d' (or numeric) to years."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    m = re.match(r'^\s*([0-9]*\.?[0-9]+)\s*([a-z]+)?\s*$', s)
    if not m:
        raise ValueError(f"Unrecognized period length: {value!r}")
    num = float(m.group(1))
    unit = (m.group(2) or "y")
    if unit in ("y", "yr", "yrs", "year", "years"):
        return num
    if unit in ("mo", "mon", "month", "months"):
        return num / 12.0
    if unit in ("w", "wk", "wks", "week", "weeks"):
        return num / 52.0
    if unit in ("d", "day", "days"):
        return num / 365.0
    raise ValueError(f"Unsupported unit in period length: {value!r}")


def _expand_absolute_yields(
    data: ProblemData,
    *,
    end_period: int,
    horizon_periods: int,
    period_length,
) -> None:
    """
    Convert yields keyed by (stratum, age_bin) into absolute-time yields keyed by (stratum, t).
    Clips to the last available bin once the stand ages beyond the table.
    """
    years_per_period = _years(period_length)

    # find max available bin per stratum
    max_bin_by_s: dict[str, int] = {}
    for (s, age_bin), _y in data.yields.items():
        max_bin_by_s[s] = max(age_bin, max_bin_by_s.get(s, 0))

    # cover the last rolling window fully
    t_max = end_period + horizon_periods
    expanded: dict[tuple[str, int], float] = {}

    for s, strat in data.strata.items():
        # your ForestStratum uses 'age'; fall back to 'age0' if present
        age0 = getattr(strat, "age", getattr(strat, "age0", 0.0))
        max_bin = max_bin_by_s.get(s, 0)

        for t in range(0, t_max + 1):
            age_years = age0 + t * years_per_period
            # if bins are one-per-period, this is floor(age / years_per_period)
            age_bin = int(age_years // years_per_period)
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
        period_length=getattr(cfg.horizon, "period_length", 10),
    )
    return data

def load_config(path: str | Path) -> PawsConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text())
    return PawsConfig(**data)