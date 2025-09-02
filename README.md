
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

## Layout

- `paws3/core/` – config, data models (Pydantic), simulator orchestration, logging
- `paws3/models/` – Pyomo builders for principal/agent/bilevel and solver adapters
- `paws3/io/` – loaders/savers; CSV/Parquet and YAML config readers
- `paws3/plugins/` – registry for behavior variants (principal policies, agent emulators, pricing rules)
- `paws3/cli/` – Typer CLI entry points mirroring FHOPS style (`*-cmd` synonyms provided)

## License
MIT
