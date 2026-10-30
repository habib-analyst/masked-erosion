# PREREG — project #107 `masked-erosion` (LOCKED before head-to-head)

Locked: 2026-10-30, after pilot (seeds 1000), after simulator freeze
(calibration seeds 2000), BEFORE any head-to-head run (seeds 5000+).
Decision rule (standing program rule, #97 lesson): **ANY locked bar
fails → KILL.** No post-hoc bar changes, no bar-shrinking, no amendments
after head-to-head data is seen. Pilot numbers below informed the design
only; confirmatory numbers come solely from the head-to-head run.

## Source paper (context only, never reported as reproduced)

arXiv 2610.38392, So/Liu/Long, "Masked Erosion". The paper's LLM-loop
figures (0.575 misuse under weaker Qwen3-30B, "lost all six" at 40-task
batches, GEPA 2/3, 411 loops) are CONTEXT ONLY. All numbers in this
build are scripted-analog numbers.

## G1 verdict (recorded here for the gate chain)

- Abs page (fetched fresh 2026-10-30): NO author code link — only
  third-party toggles (alphaXiv, CatalyzeX, DagsHub, GotitPub, Hugging
  Face, ScienceCast, Replicate, Spaces, TXYZ.AI).
- Full-text HTML (2610.38392v1, 2122 lines): ZERO `github`, ZERO
  `zenodo`, ZERO `4open`, ZERO `replication package`, ZERO
  `code is available` matches.
- One release sentence exists (Ethics, ~L423): "We will release code,
  the exact safeguard texts and proposer prompts, frozen predictions with
  hashes and run records". This is FUTURE tense with NO URL, NO host,
  NO cited package, NO downloadable artifact. Unlike #100 (an actually
  cited anonymous 4open.science replication package, present-tense
  "available at [1]"), there is no existing locatable artifact to
  duplicate, and nothing was fetched. G1 = PASS on this evidence, with
  the sentence quoted verbatim so the orchestrator can overrule.
- G1 PASS. G0 harness: deterministic, CPU-only, $0, pure-stdlib Python,
  no LLMs/APIs/GPUs. Pilot gates: (a) PASS — masked Δharm = 0.000,
  margin 2→1, weaker-policy harm rises (cred 0.0725→0.1688, ops
  0.0575→0.1494); (b) batch comparison preregistered exactly below, no
  "lost all six" chase; (c) deliverable = lattice + 10 gates + frozen
  simulator (loops are one arm, not the deliverable).

## Locked design constants

- tau = 0.05, alpha = 0.05 (McNemar one-sided), batch harm prob p = 0.1,
  audit-veto extra runs = 120, weaker-policy block reliability q = 0.7.
- Envs: cred (auth/verify/profile/caution; costs .07/.09/.11/.13;
  skill .95), ops (scope/confirm/leastpriv/dryrun; costs
  .05/.07/.09/.11; skill .93). Trap cover sets as in masked_erosion.py
  (every 3-subset covers all 8 types; every 2-subset misses exactly one).
- Execution tremble EPS = 0.05, keyed per (env, task, safeguard state).
  Pilot finding that forced this BEFORE locking: with no tremble, child
  success weakly dominates parent success on every task, so split-half
  collapsed exactly onto greedy (0.782/0.948 both). The tremble restores
  the distinction (pilot with tremble: split-half 0.636/0.759 vs greedy
  0.681/0.826) and mirrors the paper's non-bit-exact replicates.
- IUT definition (analog operationalisation, stated not as the paper's
  code): paired AND veto(1) AND margin-aware conditions jointly.
- Read-only: deletion proposals become the parent (tie → reject);
  benign edits pass through unchanged.
- Pools: 400 clean + 400 harm tasks. Batches drawn without replacement
  per generation; batch order shuffled (exchangeable halves — deliberate
  difference from the paper's harm-first ordering).
- Common random numbers: batch/proposal streams are seeded WITHOUT the
  gate name, so every gate sees identical batches and proposals for the
  same loop/decision index; audit sampling uses a separate per-gate
  stream. All paired contrasts use paired bootstrap CIs (10,000
  resamples) over the shared indices.

## Frozen simulator

- Calibration pools: seed 2000 per env (never pilot 1000, never
  head-to-head 5000+). Bootstrap resampling of calibration-pool tasks
  with replacement, exact gate code, 1000 batches per directed edge,
  chained over the lattice for loop predictions.
- File: `results/sim_predictions.json`
- SHA-256: `256660173cf8d63f01c7d03ac47d7241b5fcbc6cfc6eadfca698f86e5bb84968`
- Frozen masked-acceptance predictions (pooled H0 edges, both envs):
  n=20 — greedy .739, split-half .701, paired .038, read-only 0,
  veto-0.2 .739, veto-1 .739, audit-veto .739, margin-aware 0,
  asymmetric .038, iut 0. n=40 — greedy .862, split-half .802,
  paired .223, read-only 0, veto-0.2 .862, veto-1 .862, audit-veto .862,
  margin-aware 0, asymmetric .223, iut 0.
- Frozen loop lost-depth predictions (mean over envs): n=20 — greedy
  .995, split-half .991, paired .145, veto/audit-veto .995,
  margin-aware/read-only/iut 0. n=40 — greedy .999, split-half .998,
  paired .633, veto/audit-veto .999, margin-aware/read-only/iut 0.

## Head-to-head protocol (fresh seeds only)

- Single-deletion decisions: 400 per (env, H0 edge, n in {20, 40}), pool
  seed 7000 per env, decision seeds `h2h-dec` (gate-free → paired).
- Loops: 200 per (gate, env, n in {20, 40}), max 4 generations, pool
  seed 5000 + loop index per env, loop seeds = loop index.
- Benign decisions: 400 per (gate, env) at n=40, pool seed 7000.
- Weaker-policy eval: eval seed 11 (fresh; pilot used 7) on loop finals
  (n=40 arms).
- Free-rewrite arm (SECONDARY, not gated): 100 loops per (gate in
  {greedy, margin-aware}, env) at n=40; per-generation proposal kind
  drawn seeded 0.5 benign / 0.3 deletion / 0.2 noop, identical across
  gates. Reported descriptively only.

## Locked bars — G2 (head-to-head must satisfy ALL)

Single-deletion rates are pooled over envs + H0 edges; loop rates pooled
over envs unless noted. CIs are paired bootstrap 95% over shared indices.

- A1: greedy masked acceptance (n=40) >= 0.70. [pilot .826, sim .862]
- A2: split-half masked acceptance (n=40) >= 0.60 AND split-half minus
  greedy CI excludes 0 on the negative side (split-half < greedy).
  [pilot .759 vs .826]
- A3: veto-0.2, veto-1, audit-veto masked acceptance (n=40) each
  >= 0.70. [pilot .826, sim .862]
- A4: paired masked acceptance (n=40) >= 0.10 AND paired minus greedy
  CI excludes 0 (paired < greedy). [pilot .168, sim .223]
- A5 (batch, COST-MATCHED — same costs, only n varies): paired masked
  acceptance n=40 minus n=20, paired CI excludes 0 (positive).
  [pilot diff +.144, sim diff +.185] Direction + CI only; no magnitude
  target, no "lost all six" analog claimed (our analog has 4 safeguards).
- A6: asymmetric masked acceptance within ±0.03 of paired (same rule
  for deletions; consistency check).
- B1: margin-aware, read-only, iut loop lost-depth rate (n=40) each
  <= 0.05. [sim 0.000]
- B2: greedy minus margin-aware loop lost-depth (n=40) CI excludes 0.
  [sim .999 vs 0.000]
- B3: audit-veto loop lost-protection (n=40) <= 0.10 AND audit-veto
  loop lost-depth (n=40) >= 0.50 (audits prevent exposure but NOT
  depth loss). [sim 0.000 / 0.999]
- B4: greedy loop lost-protection (n=40) >= 0.50. [sim 0.985]
- B5 (batch at loop level): paired loop lost-depth n=40 minus n=20,
  paired CI excludes 0 (positive). [sim .633 - .145 = +.488]
- C1: simulator MAE across the 10 gates' masked-acceptance rates
  (n=40, head-to-head single-deletion) <= 0.12.
- C2: >= 8/10 gates' predicted masked-acceptance within ±0.15 of
  observed (n=40).
- C3: loop lost-depth prediction within ±0.20 of observed for >= 8/10
  gates (n=40, pooled envs).
- C4 (qualitative ordering, observed): greedy, veto-0.2, veto-1,
  audit-veto each > paired; margin-aware, read-only, iut each <= 0.05
  masked acceptance (n=40).
- D1: margin-aware benign acceptance >= greedy benign acceptance
  minus 0.05 (paired CI on the difference must not exclude a larger
  shortfall; equivalently the point difference >= -0.05 and the CI
  lower bound >= -0.10). [pilot both .980]
- D2: margin-aware loop-final clean success >= 0.95 x initial (H0)
  clean success, mean over loops (n=40). [loops never accept deletions
  under margin-aware, so final = initial exactly, up to pool noise]
- W1 (weaker-policy reuse, n=40 loop finals): mean weaker-policy harm
  of greedy finals minus margin-aware finals, paired CI excludes 0
  (positive). [greedy finals mostly low-margin states, weaker harm
  ~0.33; margin-aware finals stay at H0, weaker harm ~0.065]

## Locked bars — G3 (validity)

- Unit tests green (10/10 at lock; re-run after head-to-head).
- Determinism: head-to-head headline rerun byte-identical (same seeds
  → same headline.json bytes except recorded hashes/timestamps, which
  are excluded by re-running the computation and comparing the numbers
  object).
- SHA-256 of `results/headline.json` recorded in KILLGATE.md.

## Scope honesty (applies to PAPER.md and the LinkedIn draft)

- Scripted-analog numbers only. The weaker-policy arm is a DEFINED
  scripted policy (noisy per-safeguard blocking), NEVER a real model
  swap. No claim about AppWorld, OpsSim, GEPA, Qwen, or any LLM.
- IUT is our operationalisation, not the paper's code.
- The batch result is cost-matched and directional; the paper's
  "20 kept / 40 lost all six" is context, not a target.
