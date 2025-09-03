# paws3/src/paws3/io/csv_loader.py
from __future__ import annotations
import csv
from pathlib import Path
from loguru import logger
from ..core.datatypes import ProblemData, ForestStratum, PeriodDemand

def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        return [dict(r) for r in rdr]

def load_problem_data_from_csvs(data_dir: str) -> ProblemData:
    dp = Path(data_dir)

    # strata.csv: id,species,area,age
    strata_rows = _read_csv(dp / "strata.csv")
    strata = {
        r["id"]: ForestStratum(
            id=r["id"],
            area=float(r["area"]),
            species=r.get("species", "PINE"),
            age=int(float(r.get("age", 0))),
        )
        for r in strata_rows
    }

    # yields.csv: stratum,period,yield_m3_per_ha[,age_years]
    yields_rows = _read_csv(dp / "yields.csv")
    yields: dict[tuple[str,int], float] = {}
    for r in yields_rows:
        s = r.get("stratum") or r.get("id") or r.get("stratum_id")
        t = int(float(r["period"]))
        y = float(r.get("yield_m3_per_ha") or r.get("m3_per_ha") or r.get("yield"))
        yields[(s, t)] = y

    # demand.csv: period,species,min_vol,max_vol
    demand_rows = _read_csv(dp / "demand.csv")
    demand = [
        PeriodDemand(
            period=int(float(r["period"])),
            species=r.get("species", "PINE"),
            min_vol=float(r.get("min_vol", 0.0)),
            max_vol=float(r.get("max_vol", 1e9)),
        )
        for r in demand_rows
    ]

    # Optional: prices.csv (species,price) and costs.csv (name,value)
    prices_path = dp / "prices.csv"
    costs_path  = dp / "costs.csv"
    prices = {"PINE": 100.0}
    costs  = {"harvest": 50.0}

    if prices_path.exists():
        prices = {r["species"]: float(r["price"]) for r in _read_csv(prices_path)}
    if costs_path.exists():
        costs = {r["name"]: float(r["value"]) for r in _read_csv(costs_path)}

    # Helpful logging
    ts = [t for (_, t) in yields.keys()]
    logger.info(
        "Loaded CSV data: |S|={} |Y|={} t∈[{}..{}] |D|={} prices={} costs={}",
        len(strata), len(yields), min(ts) if ts else None, max(ts) if ts else None,
        len(demand), prices, costs
    )

    return ProblemData(strata=strata, yields=yields, demand=demand, prices=prices, costs=costs)