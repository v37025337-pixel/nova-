# Digital Mind Development V1

## Objective

Develop a measurable digital mind that researches deficits, learns and writes
algorithms/rules, tests them out-of-sample, applies them, chooses goals, plans,
predicts outcomes, calibrates uncertainty, invents mechanisms, transfers them,
and preserves a causal self-history.

No capability is real until independently validated.

## Program status

1. **DM01 Contextual Belief Arbitration -> M0013** — COMPLETED
2. **DM02 Causal Self-Model -> M0014** — COMPLETED
3. **DM03 Self-Learning & Algorithm Genesis -> M0015** — COMPLETED
4. **DM04 Goal & Interest Architecture -> M0016** — COMPLETED
5. **DM05 Planning & Replanning -> M0017** — COMPLETED
6. **DM06 Counterfactual World Model -> M0018** — COMPLETED
7. **DM07 Metacognition & Calibration -> M0019** — COMPLETED
8. **DM08 Generic Mechanism Genesis -> M0020** — ACTIVE
9. **DM09 Cross-Domain Cognitive Transfer -> M0021** — PENDING
10. **DM10 Persistent Self-History -> M0022** — PENDING
11. **DM11 Autonomous Cognitive Evolution -> M0023** — PENDING

## Learned artifacts

### LRA-1 — relation generalization
Artifact hash:
`8f2b695f118e9d4f2cea1e2981b10fca4abf1c0c736629cf715f2bfed87322a8`

### GSA-1 — goal selection
Artifact hash:
`bcd618eb065e1b475fceb802095ea5f452e12cbbc080981147bd7701cdea7a75`

Development:
- 13 trade-off cases
- train accuracy 1.00
- held-out accuracy 1.00
- hard cost/risk budgets enforced

Independent M0016 admission:
- 3 / 3 PASS
- program dependency
- hard budget exclusion
- no-feasible-goal behavior

### PRA-1 — planner/replanner
Artifact hash:
`1ad0066899251df7a6f9becd2b16cbd1c6124937f294d74494cd4f69ce19e45f`

Configuration:
```
SEARCH astar_goal_count
HEURISTIC_WEIGHT 0.5
COST_WEIGHT 0.5
MAX_EXPANSIONS 100
LOOP_DETECTION state_hash
ON_FAILURE block_failed_action_and_replan
REPLAN_FROM observed_current_state
```

Development:
- train 4 / 4
- held-out 6 / 6
- replanning rate 1.00
- loop detection PASS
- unsolvable case returns no_plan

Independent M0017 admission:
- 3 / 3 PASS

### CFM-1 — counterfactual runtime model
Artifact hash:
`f7917daba9f9e54a906841c97bad6aa75afbd4d04356d27366f7c92d31a6faf4`

Development:
- six predictions frozen before six real runtime actions
- accuracy 1.00
- multiclass Brier 0.00
- prediction errors 0
- fresh application PASS

Independent M0018 admission:
- freeze SHA:
  `8c4b5a488db7784668983bb0e19d3a4644596cc4fbe0d36cc350c1e398dd1d79`
- 6 / 6 PASS
- Brier 0.00

### MCA-1 — metacognitive calibrator
Artifact hash:
`4da60376b0bd08d3335d33399bfa56076d7b5e03f46c1fa6c98f9ce54231445c`

Development:
- train accuracy 1.00
- held-out accuracy 1.00
- ECE 0.00
- Brier 0.00
- correctly used UNRESOLVED 3 times
- correctly requested missing evidence

Independent M0019 admission:
- 3 / 3 PASS
- browser capability -> ANSWER
- under-scoped Node-API conflict -> UNRESOLVED + request scope evidence
- future PyPI state -> UNRESOLVED + request future observation

## Current step — DM08

Target:
`M0020:mechanism-genesis`

Required admission evidence:
- at least three new mechanisms produced through the generic genesis process
- every mechanism has an independent evaluator
- at least one full REJECT -> REDESIGN -> ADMIT chain
- no candidate/evaluator hidden-answer leakage

## Rules

- Research before synthesis.
- Freeze predictions/rules before held-out observations.
- REJECT and UNRESOLVED are valid.
- Preserve prior model/artifact versions.
- No arbitrary eval/shell/network inside learned DSL artifacts.
- Production requires independent admission.
- Confidence must be calibrated against observed outcomes.
- No hidden-weight/private-reasoning claims.

## DM08 local implementation increment (2026-10-05)

A bounded rule-genesis shadow kernel and independent held-out evaluator are now
available in source; see [GENESIS.md](GENESIS.md) for reproduction and limitations.
The synthetic exercise retains a 5/7 rejection, generates a redesigned rule from
a separate public training batch, and obtains 11/11 on a distinct held-out suite.
The public example is reproducible and is not production admission evidence.
DM08 stays ACTIVE; three new mechanisms, real-task evaluation and Deno/Supabase
integration remain outstanding. No automatic production admission is enabled.
