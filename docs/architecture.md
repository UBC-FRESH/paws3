
# PAWS3 Architecture (WS3 + FHOPS integration)

## Roles
- **Principal (WS3 emulator)**: produces first-period commitments (volumes by stratum/product).
- **Agent (FHOPS)**: consumes commitments + blocks; returns feasible schedule & realized flows/costs.

## Interfaces (Pydantic models)
- `PrincipalDecision`: {period, commitments[(stratum, product)] -> volume}
- `AgentRequest`: {period, blocks[], commitments[]}
- `AgentResponse`: {period, summary{status, solver, cost...}, schedule[]}

## Adapters
- `adapters.ws3_adapter.WS3Principal`: `mode=import|cli`
- `adapters.fhops_adapter.FHOPSAgent`: `mode=import|cli`

## Rolling-horizon loop
t = start
while t < end:
  pdec = WS3Principal.plan_first_period(state_t)
  areq = map(pdec)  # commitments -> blocks
  aresp = FHOPSAgent.schedule_first_period(areq)
  state_{t+1} = apply(aresp)  # update inventory, capacities, and commitments
  t += replanning_step

## Notes
- Period alignment: WS3 often in years; FHOPS in days. Use `period_length` and mapping functions (to be implemented).
- Bilevel: keep `decomposition` path as default for MIP agents (FHOPS).
- Provenance: log configs, seeds, solver versions, and output artifacts per run folder.
