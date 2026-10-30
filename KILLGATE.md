# KILLGATE — project #107 `masked-erosion`

**Verdict: PASS — all gates green, no bar moved, no bar shrunk.**
Staged payload only. **REPO NEEDED: `habib-analyst/masked-erosion`**
(no push made; GitHub App cannot create repos).

## Per-gate verdicts

- **G0 harness: PASS.** Deterministic, CPU-only, $0, pure-stdlib Python
  (3.12). No LLMs, APIs, GPUs, or real agent environments. Scripted
  agents, four overlapping safeguards × two synthetic environments,
  deterministic 16-subset harm lattice, ten gate rules as pure code,
  batch-size sweep, defined-scripted weaker-policy arm.
- **G1 author-code recheck: PASS (with a recorded caveat).**
  Abs page fetched fresh 2026-10-30: no author code link, only
  third-party toggles. Full-text HTML (2610.38392v1, 2122 lines):
  ZERO `github`, ZERO `zenodo`, ZERO `4open`, ZERO `replication
  package`, ZERO `code is available`. One release sentence exists
  (Ethics, ~L423): "We will release code, the exact safeguard texts and
  proposer prompts, frozen predictions with hashes and run records" —
  FUTURE tense, no URL, no host, no cited package, no downloadable
  artifact. Unlike #100 (an actually cited anonymous 4open.science
  replication package, present-tense "available at [1]"), there is no
  existing locatable artifact to duplicate, and nothing was fetched.
  The sentence is quoted verbatim in PREREG.md so the orchestrator can
  overrule this reading; on the evidence available at build time, G1
  passes. (If the authors later publish a located package, this build
  should be re-examined under the #100 precedent.)
- **Pilot gate: PASS.**
  (a) Masked deletion exhibited: H0-edge deletions change harm by
  exactly 0.000 while margin falls 2 → 1, and weaker-policy harm rises
  (cred 0.0725 → 0.1688, ops 0.0575 → 0.1494).
  (b) The 20-vs-40 batch result was preregistered exactly (direction +
  paired CI exclusion, cost-matched, same costs, only n varies); the
  paper's "lost all six" headline was not chased (our analog has 4
  safeguards, and loop counts differ by design).
  (c) The deliverable IS the lattice + gate comparison + frozen
  simulator: the loop arm is one measurement arm, and the free-rewrite
  arm is explicitly secondary and ungated.
- **G2 disease + G3 load-bearing mechanism: PASS — all 18 PREREG bars
  true** (auto-graded by `run_head2head.py` on fresh seeds; see
  `results/headline.json`):
  - A1 greedy masked acceptance (n=40) 0.859 ≥ 0.70.
  - A2 split-half 0.789 ≥ 0.60, split-half − greedy CI [−0.079, −0.061]
    (excludes 0, negative side).
  - A3 veto-0.2 / veto-1 / audit-veto 0.859 each ≥ 0.70.
  - A4 paired 0.197 ≥ 0.10, paired − greedy CI [−0.678, −0.645].
  - A5 paired n=40 − n=20 CI [0.144, 0.174] (excludes 0, positive).
  - A6 asymmetric 0.197, within 0.000 of paired (≤ 0.03).
  - B1 margin-aware / read-only / IUT loop lost-depth (n=40) 0.000
    each ≤ 0.05.
  - B2 greedy − margin-aware loop lost-depth CI [1.000, 1.000].
  - B3 audit-veto loop lost-protection 0.000 ≤ 0.10 AND lost-depth
    1.000 ≥ 0.50.
  - B4 greedy loop lost-protection 0.992 ≥ 0.50.
  - B5 paired loop lost-depth n=40 − n=20 CI [0.357, 0.477].
  - C1 simulator masked-acceptance MAE 0.008 ≤ 0.12.
  - C2 10/10 gates within ±0.15 (max error 0.026) ≥ 8/10.
  - C3 10/10 gates' loop lost-depth predictions within ±0.20
    (max error 0.050) ≥ 8/10.
  - C4 ordering holds: greedy/veto/audit-veto (0.859) > paired (0.197);
    margin-aware/read-only/iut 0.000 ≤ 0.05.
  - D1 margin-aware benign acceptance 0.971 = greedy 0.971
    (difference 0.000, within −0.05).
  - D2 margin-aware final/initial clean-success ratio 1.000 ≥ 0.95.
  - W1 weaker-policy harm, greedy finals − margin-aware finals,
    CI [0.716, 0.762] (excludes 0).
- **Tests: PASS.** 10/10 unit tests green (lattice shape, masked
  zero-harm, weaker-policy rise, McNemar boundary, read-only rejection,
  margin-aware masked-reject/benign-accept, all-gates-bool,
  determinism, Wilson).
- **Determinism: PASS.** Head-to-head executed three times: one
  reporting crash (no file written) + two successful writes. The two
  successful writes agree on every top-level key except `cis` (the
  three restored CI entries — see below): pooled single-deletion rates,
  pooled loop summaries, and all 18 bar verdicts identical.
- **SHA-256:** `results/headline.json` =
  `3015305f18fd825987f2e3c2fd297b991b777121386ebb801dfc6cab4c60e623`
  (final run); `results/sim_predictions.json` =
  `256660173cf8d63f01c7d03ac47d7241b5fcbc6cfc6eadfca698f86e5bb84968`
  (frozen before head-to-head; recorded in PREREG.md).

## Honest reporting notes (not gate failures)

1. **Reporting-fix disclosure (no data change, no re-grading).**
   Two reporting bugs in sequence, both fixed in the script, neither
   touching data or bars:
   - Run A crashed at the reporting step (KeyError: the B2/B5/W1 CI
     block wrote into `H["cis"]` before that dict was created) —
     after all computation but before writing, so run A wrote nothing.
     Fix: initialise `"cis": {}` in the results dict.
   - Run B completed with all 18 bars PASS, but a later dict-literal
     assignment (`H["cis"] = {...}`) overwrote the dict and dropped
     the B2/B5/W1 CI values from the written file. Bar verdicts were
     unaffected — they were computed from local variables before the
     overwrite — but the file was incomplete. Fix: one word
     (`H["cis"].update(...)` instead of `H["cis"] = {...}`).
   - Run C (determinism re-run) wrote the complete headline. Run B's
     file was preserved as `headline_run1.json`; the B-vs-C comparison
     shows every top-level key identical except `cis` (exactly the
     three restored entries), pooled rates and loop summaries
     identical, all 18 bars identical. Bar verdicts were computed by
     the script in every run, never by hand.
2. **Pre-registration discipline.** The tremble (EPS = 0.05) and the
   IUT operationalisation were design decisions made and documented
   BEFORE PREREG was locked (the tremble fixed a pilot finding that
   split-half collapsed exactly onto greedy without noise). No bar,
   constant, or analysis choice changed after head-to-head data was
   seen. Zero PREREG amendments.
3. **Veto = greedy for masked deletions is substantive, not a bug.**
   Veto gates audit child-only harm; masked deletions show exactly
   zero child-only harm, so no audit share can ever catch them. The
   equality (0.859 = 0.859) is the mechanism, and it is why audit-veto
   loses depth in 100% of loops while losing protection in 0%.
4. **Weaker-policy finals above H0 level for margin-aware arms.**
   Margin-aware/read-only/iut finals show weaker harm 0.080 (cred) /
   0.075 (ops) vs the pilot pools' H0 0.0725 / 0.0575 — pool variation
   across fresh loop pools, not depth loss: those finals ARE the full
   stack (margin 2.0, lost-depth 0.0). The comparison that matters is
   against greedy finals (0.873 / 0.759), CI [0.716, 0.762].
5. **Scope limits.** Scripted analog only; IUT is our
   operationalisation; the weaker-policy arm is a defined scripted
   policy, never a model swap; the batch result is cost-matched and
   directional. The paper's AppWorld/OpsSim/GEPA/LLM figures are
   context only.

## Compute

$0. CPU only. Pilot ~48 s, simulator ~5 min, head-to-head ~4–6 min per
run, all on this VM.
