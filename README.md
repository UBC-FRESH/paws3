
# PAWS3 — Principal-Agent Wood Supply Simulation System

**PAWS3** (pronounced "paws") is a modular Python framework for **rolling-horizon simulated replanning**
of forest management under **principal–agent** dynamics, with an optional **bilevel** model coupling
(government "principal" upper level; industrial "agent" lower level). It is designed to align with
the **FHOPS** package structure and CLI conventions to minimize onboarding cost across projects.

- Backbone: **Pyomo**
- Solvers: **HiGHS** (LP/MIP) via `highspy` or `appsi` (exec fallback supported)
- Patterns: strategy/plug‑in behaviors for principal/agent variants; clean separation of data, model,
  and simulation orchestration
- Variants supported: myopic upper-level, anticipative upper-level with explicit agent model, bilevel
  reformulations, rolling-horizon windowing and re-optimization

## Quick start

```bash
# install (editable)
pip install -e .

# initialize a new project space with example config & data
paws3 init examples/minimal

# run a rolling-horizon simulation (myopic principal; dummy agent emulator)
paws3 run-sim --config examples/configs/minimal.yaml

# run bilevel (stub lower-level; for scaffolding validation)
paws3 solve-bilevel --config examples/configs/bilevel_stub.yaml
```

## Package Module Layout

- `paws3/core/` – config, data models (Pydantic), simulator orchestration, logging
- `paws3/models/` – Pyomo builders for principal/agent/bilevel and solver adapters
- `paws3/io/` – loaders/savers; CSV/Parquet and YAML config readers
- `paws3/plugins/` – registry for behavior variants (principal policies, agent emulators, pricing rules)
- `paws3/cli/` – Typer CLI entry points mirroring FHOPS style (`*-cmd` synonyms provided)


## Why this exists

- **Fast iteration:** You can start from tiny CSVs (strata, yields, demand) and get a working simulation loop without standing up a database or a giant codebase.
- **Explicit structure:** The rolling‑horizon loop is deliberately simple and readable; the UL/LL interface is narrow and typed so you can swap in different models.
- **Research‑friendly:** Add constraints/objectives, try even‑flow vs. revenue maximization, prototype decomposition/stubbed LLs, and record commits each period.


## Architecture at a glance

```
CSV data ──► ProblemData ──► RollingHorizonSimulator
                        ╰──► Principal (UL) model  ──► first‑period commitments
                                   ╰───────────────► Agent / Lower‑Level (LL) behavior (stub or FHOPS)
```

- **Data layer (`io/`)**
  - `csv_loader.py` reads small CSVs into a `ProblemData` object:
    - `strata.csv`: `stratum_id, area, species, age`
    - `yields.csv`: `stratum_id, age_bin, yield_m3_per_ha`
    - `demand.csv`: `period, species, min_vol, max_vol`
  - `_expand_absolute_yields(...)` converts age‑bin yields into **absolute‑time** yields for all simulated periods (e.g., “10y” bins → t=0..T).

- **Core (`core/`)**
  - `config.py` defines typed `PawsConfig` (horizon, solver, policies, data path).
  - `sim.py` has `RollingHorizonSimulator` which:
    1. Loads `ProblemData`
    2. Loops periods `t = start .. end`
    3. Builds/solves the principal model on the current window `[t, t+H-1]`
    4. Extracts **first‑period commitments** (UL→LL)
    5. Invokes **agent behavior** (LL) to emulate consumption/market response
    6. Advances to next period and repeats

- **Models (`models/`)**
  - `principal.py` contains the upper‑level Pyomo model (clean LP by default).
  - `bilevel.py` manages the UL/LL handoff. Today a **stub LL** is provided; you can drop in a full FHOPS or decomposition later.


## Principal (Upper‑Level) model

Default decisions/logic (simple and readable; change as you like):

- **Decision variable:** `X[s,t]` = harvested **area (ha)** in stratum *s* during absolute period *t* (within the rolling window).
- **Volume expression:** `vol[t] = Σ_s X[s,t] · yield[s,t]` (m³/ha × ha).
- **Area conservation:** `Σ_t X[s,t] ≤ area[s]` (can’t harvest more than stand area over the window).
- **Physical cap (safety):** `vol[t] ≤ Σ_s area[s] · yield[s,t]`.
- **Demand bounds (optional):** from `demand.csv` if periods fall in the window.
- **Even‑flow policy (optional):** enforce **minimum flow on the first step only** (`vol[t0] ≥ min_vol`) to avoid infeasibility later.
- **Objective (default):** maximize total volume over the window: `max Σ_t vol[t]`.
  - Swap in even‑flow (L1 deviations) or revenue objectives easily.

**First‑period commitments.** After solving, the simulator extracts per‑stratum volume at `t0` and publishes a compact mapping like:
```
{ (stratum_id, "sawlog") : committed_volume_m3, ... }
```
If per‑stratum is zero but the aggregate is positive, it falls back to `{("ALL", "sawlog"): vol_t0}`.


## Lower‑Level (Agent) behavior

- The LL currently defaults to a **stub** that simply acknowledges principal commitments.
- A pluggable `agent_behavior` hook allows emulating consumption, deliveries, and pricing rules (e.g., profit-max or contractual take‑or‑pay).
- You can replace the stub with a full **FHOPS** or other detailed mill/contract model; `bilevel.py` keeps the interface narrow.


## Rolling‑Horizon flow

1. **Windowing.** At absolute time `t`, solve the UL on `[t, t+H-1]` (H = `horizon_periods`).
2. **Commit.** Extract and record only **t**’s decision (first‑period commitment).
3. **React.** Run the LL behavior to emulate what actually ships/consumes at time `t`.
4. **Advance.** Move to `t+replanning_step`, rebuild, and repeat until `end_period`.

This mirrors real planning where only today’s decision is binding; future periods are re‑optimized as new information arrives.


## Inputs & configuration

- **CSV data:** put under `examples/minimal/data` (or your own path).
- **Config YAML:** choose horizon, policies, solver, and paths. Example:
```yaml
horizon:
  period_length: "10y"     # or 7, "6mo", "52w", "7d"
  horizon_periods: 10
  replanning_step: 1
  start_period: 0
  end_period: 24

principal_policy:
  name: even_flow
  params:
    min_vol: 5000

agent_behavior:
  name: profit_max_flow_stub
  params: {}

bilevel:
  enabled: true
  reformulation: decomposition

solver:
  driver: appsi
  time_limit: 30    # seconds

run:
  random_seed: 42
  log_level: INFO
  out_dir: examples/minimal/runs

data_path: examples/minimal/data
```


## Outputs

- **Console logs** per period/window (UL cap, chosen flow, commitments, LL response).
- **Structured results** (planned) available from the simulator (e.g., for tests or notebooks).
- You can add CSV/Parquet writers or plots in the run loop if needed.


## Extending PAWS3

- **Objectives/constraints:** Edit `models/principal.py` to add even‑flow (L1/L2), revenue terms, carbon constraints, adjacency, road/opening costs, etc.
- **Lower‑level detail:** Replace the stub with an MILP for contracts, mill capacities, grades, or multi‑product flows.
- **Data:** Add more columns/tables; expand `ProblemData` and the CSV reader.
- **Decomposition:** Keep the UL/LL interface stable while experimenting with different bilevel reformulations.


## Current limitations / notes

- LL is a **stub** by default; market clearing and contracts are illustrative.
- Yields are assumed **per‑period** (m³/ha) and expanded from age‑bins to absolute time with a simple clip‑to‑last‑bin rule.
- The demo uses **one product label** (`"sawlog"`) for commitments; generalize as needed.
- No stochasticity or Bayesian updates yet (but you can inject them in the loop).


## Quick start

```bash
# From repo root
paws3 solve-bilevel --config examples/configs/bilevel_stub.yaml -v
```

You should see a rolling sequence of windows, first‑period commitments, and (stub) agent responses.


## Mental model / terminology

- **Stratum**: a stand/age class with an area, species, and starting age.
- **Yield**: m³/ha for a stand at a given age bin (expanded to absolute time).
- **Commitment**: the UL’s binding volume decision at the current period.
- **Agent**: the LL process consuming or allocating the committed volume.
- **Window**: the local planning horizon used at each simulation step.


## Status

This codebase is intentionally small and evolving. Expect rough edges in logging and config until the interfaces stabilize. Contributions and issue reports are welcome.


## License
MIT
