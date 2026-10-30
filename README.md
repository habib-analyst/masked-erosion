# masked-erosion — scripted analog of arXiv 2610.38392

**What the paper claims (context only):** self-improving agents keep a
harness edit only if an acceptance gate scores it higher on a task batch.
When safeguards overlap, deleting one is *masked* — the others still block
the harm — so the gate decides on task success alone and redundancy erodes
unseen. The paper formalises *margin* (fewest further deletions before
harm appears), measures harm for all 16 subsets of four safeguards in two
environments, and runs 411 loops under ten gate rules plus three GEPA runs,
with a gate simulator frozen before the loops predicting where each gate
breaks.

**What this repo is:** a deterministic, CPU-only, $0 scripted analog. No
LLMs, no APIs, no GPUs, no real AppWorld/OpsSim. The paper's LLM-loop
figures (0.575 misuse under weaker Qwen3-30B, "lost all six" at 40-task
batches, GEPA 2/3, 411 loops) are **context only and are never presented
as reproduced**. Every number here comes from the scripted analog below.

## The analog in 60 seconds

- Two synthetic environments, four safeguards each, mirroring the paper's
  layers: `cred` (auth/verify/profile/caution — credential-misuse analog)
  and `ops` (scope/confirm/leastpriv/dryrun — destructive-clean-up analog).
- Eight trap types per env. Cover sets are chosen so **every** single
  deletion from the full stack stays fully covered (harm 0) while
  **every** two-deletion subset leaves exactly one trap type uncovered
  (harm 1/8 = 0.125 > tau = 0.05). Hence margin(full stack) = 2,
  margin(3 safeguards) = 1, margin(2 or fewer) = 0 (unprotected).
- Each safeguard costs clean-task success, so deleting one genuinely
  raises batch success (selection regime) — which is exactly what lets
  success-based gates accept masked deletions.
- Harm tasks: blocked if any covering safeguard is present (safe
  completion); unblocked → harm via a harmful shortcut. Child-only harm
  is therefore exactly 0 for masked deletions and 1/8 per uncovered type
  for exposing deletions.
- Weaker-policy reuse arm: a **defined scripted policy** in which each
  covering safeguard independently fails to block with probability 0.3
  (q = 0.7), keyed deterministically by (seed, task, safeguard). It is
  NOT a model swap and is never described as one.
- Ten gate rules as pure code (paper Table 1 + App. B): greedy,
  split-half, paired (exact one-sided McNemar, alpha = 0.05), read-only,
  veto(rho = 0.2), veto(rho = 1), audit-veto (120 extra harm runs),
  margin-aware (greedy + every one-layer ablation of the child stays
  protected), asymmetric (weakening candidates → paired, rest → greedy),
  IUT. **IUT is our operationalisation** (paired + veto(1) +
  margin-aware jointly) — the paper's exact IUT code is unreleased, so
  this is stated as an analog definition, not a reproduction.
- Execution tremble EPS = 0.05 per (task, state), added before
  preregistration after a pilot finding: with no tremble, child success
  weakly dominates parent success on every task, so split-half collapsed
  exactly onto greedy. Harm is never trembled.

## Headline results (head-to-head, fresh seeds; PREREG-locked, all bars PASS)

Single-deletion acceptance, masked deletions, n = 40 (3,200 decisions per
gate, pooled over envs + edges):

| Gate | Accepted |
|---|---|
| greedy | 0.859 |
| split-half | 0.789 |
| paired (McNemar) | 0.197 |
| veto (0.2 / 1) / audit-veto | 0.859 each |
| margin-aware / read-only / IUT | 0.000 each |
| asymmetric | 0.197 (= paired, same rule for deletions) |

- Batch size, cost-matched: paired masked acceptance rises 0.038 (n = 20)
  → 0.197 (n = 40), paired difference CI [0.144, 0.174] — direction and
  CI preregistered, no magnitude chased, no "lost all six" analog claimed.
- Loops (200 per gate/env/n, 4 generations): greedy loses depth in
  100% of n = 40 loops and loses protection in 99.2%; audit-veto loses
  protection in 0% but loses depth in 100% — **audits prevent exposure
  but not depth loss**, the paper's central remedy finding in analog
  form. Margin-aware / read-only / IUT lose depth in 0% of loops.
  Paired loop lost-depth rises 0.165 (n = 20) → 0.583 (n = 40), CI on the
  difference [0.357, 0.477].
- Weaker-policy reuse (eval seed 11): greedy-loop finals harm at 0.873
  (cred) / 0.759 (ops) vs margin-aware finals at 0.080 / 0.075 —
  difference CI [0.716, 0.762]. Depth lost under the loop model becomes
  harm under the weaker policy, while strong-policy harm stays 0.
- Benign bound: margin-aware accepts genuinely improving, non-harmful
  edits at 0.971, exactly the greedy rate (difference 0.000), and
  margin-aware loop-final clean success equals initial success (ratio
  1.000) — the remedy costs no utility on benign edits.
- Frozen simulator (calibration seeds 2000, frozen before head-to-head):
  masked-acceptance MAE 0.008 across gates (max per-gate error 0.026);
  loop lost-depth error ≤ 0.050 for all 10 gates. The simulator
  predicted the break ordering before any loop ran.

## Reproduce

```bash
python3 -m unittest discover -s tests          # 10/10 green
python3 run_pilot.py                            # pilot seeds 1000
python3 run_simulator.py                        # calibration seeds 2000 -> results/sim_predictions.json
python3 run_head2head.py                        # fresh seeds 5000+/7000 -> results/headline.json
```

Determinism: the head-to-head run was executed three times (one
reporting crash writing nothing, then two successful writes); the two
successful writes agree exactly (pooled rates, loop summaries, all 18
bar verdicts identical; only restored CI entries differed, see
KILLGATE.md).
SHA-256(`results/headline.json`) =
`3015305f18fd825987f2e3c2fd297b991b777121386ebb801dfc6cab4c60e623`.
SHA-256(`results/sim_predictions.json`) =
`256660173cf8d63f01c7d03ac47d7241b5fcbc6cfc6eadfca698f86e5bb84968`.
Compute: $0, CPU only. No repo push from this build (REPO NEEDED:
`habib-analyst/masked-erosion`).

## Files

- `masked_erosion.py` — environments, harm lattice, margin, 10 gates,
  loops, weaker-policy arm, Wilson + paired-bootstrap stats.
- `run_pilot.py`, `run_simulator.py`, `run_head2head.py` — the three
  stages, with strictly separated seed ranges.
- `PREREG.md` — locked bars + decision rule (ANY locked bar fails → KILL).
- `KILLGATE.md` — per-gate verdicts, hashes, and honest limitations.
- `results/` — `pilot.json`, `sim_predictions.json`, `headline.json`
  (+ `headline_run1.json`, the first head-to-head run, kept for the
  determinism comparison).
- `tests/test_masked_erosion.py` — lattice, gate, and determinism tests.
