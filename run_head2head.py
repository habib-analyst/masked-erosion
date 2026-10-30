"""Head-to-head run (FRESH seeds only; PREREG-locked bars auto-graded).

- Single-deletion decisions: pool seed 7000/env, 400 per (env, H0 edge, n).
- Loops: 200 per (gate, env, n), pool seed 5000 + loop index per env.
- Benign decisions: 400 per (gate, env) at n=40, pool seed 7000.
- Weaker-policy eval: eval seed 11 on n=40 loop finals.
- Free-rewrite arm (secondary, descriptive): 100 loops per gate in
  {greedy, margin-aware} per env at n=40.
Pairing: single-deletion/benign decisions share the identical batch across
gates (paired bootstrap over decision indices); loops share pool +
batch/proposal streams across gates for the same (env, index, n)
(paired bootstrap over loop indices); cross-n loop contrasts share only
the pool (same index), which is stated wherever used.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masked_erosion import (GATES, LAYERS, TaskPool, _seeded_rng, clean_success,
                            decide_gate, draw_batch, full_lattice,
                            paired_outcomes, paired_bootstrap_ci, run_loop,
                            weaker_harm, wilson)

BASE = Path(__file__).resolve().parent
OUT = BASE / "results" / "headline.json"
N_DEC = 400
N_LOOPS = 200
N_REWRITE = 100


def rate(acc, n):
    lo, hi = wilson(acc, n)
    return {"acc": acc, "n": n, "rate": acc / n, "wilson": [lo, hi]}


def main():
    H = {"single_deletion": {}, "single_diffs": {}, "loops": {},
         "loop_diffs": {}, "benign": {}, "benign_diffs": {},
         "weaker": {}, "rewrite": {}, "bars": {}, "cis": {}}
    # ---- single-deletion + benign (shared batches across gates) ----
    for env in ("cred", "ops"):
        pool = TaskPool.build(env, 7000)
        full = frozenset(LAYERS[env])
        for n in (20, 40):
            for victim in LAYERS[env]:
                child = full - {victim}
                acc = {g: 0 for g in GATES}
                diffs = {g: [] for g in GATES}
                for d in range(N_DEC):
                    rng = _seeded_rng("h2h-dec", env, victim, n, d)
                    batch = draw_batch(pool, rng, n)
                    rows = paired_outcomes(env, full, child, batch)
                    dec = {}
                    for g in GATES:
                        audit_rng = _seeded_rng("h2h-audit", g, env, victim,
                                                n, d)
                        dec[g] = decide_gate(g, env, pool, full, child,
                                             batch, rows, audit_rng,
                                             kind="deletion")
                        acc[g] += int(dec[g])
                    for g in GATES:
                        diffs[g].append(dec[g])
                for g in GATES:
                    H["single_deletion"][f"{env}|{victim}|n{n}|{g}"] = rate(
                        acc[g], N_DEC)
                H["single_diffs"][f"{env}|{victim}|n{n}"] = diffs
        for g in GATES:
            acc = 0
            decs = []
            for d in range(N_DEC):
                rng = _seeded_rng("h2h-ben", env, d)
                batch = draw_batch(pool, rng, 40)
                rows = paired_outcomes(env, full, full, batch, kind="benign")
                audit_rng = _seeded_rng("h2h-ben-audit", g, env, d)
                dec = decide_gate(g, env, pool, full, full, batch, rows,
                                  audit_rng, kind="benign")
                acc += int(dec)
                decs.append(int(dec))
            H["benign"][f"{env}|{g}"] = rate(acc, N_DEC)
            H["benign_diffs"][f"{env}|{g}"] = decs
    # ---- loops (per-loop compact arrays retained for paired CIs) ----
    H["loop_arrays"] = {}
    H["init_clean"] = {}
    for env in ("cred", "ops"):
        for n in (20, 40):
            loops = {g: [] for g in GATES}
            for j in range(N_LOOPS):
                pool = TaskPool.build(env, 5000 + j)
                lat = full_lattice(env, pool)
                H["init_clean"][f"{env}|{j}"] = clean_success(
                    env, pool, frozenset(LAYERS[env]))
                for g in GATES:
                    r = run_loop(env, pool, g, seed=j, n=n, lattice=lat)
                    loops[g].append({
                        "lost_depth": int(r["lost_depth"]),
                        "lost_protection": int(r["lost_protection"]),
                        "final_margin": r["final_margin"],
                        "final_clean": r["final_clean_success"],
                        "final_state": r["final_state"],
                        "masked_accepted": r["masked_accepted"]})
            for g in GATES:
                ls = loops[g]
                H["loop_arrays"][f"{env}|{g}|n{n}"] = ls
                H["loops"][f"{env}|{g}|n{n}"] = {
                    "lost_depth": sum(l["lost_depth"] for l in ls) / N_LOOPS,
                    "lost_protection": sum(l["lost_protection"] for l in ls)
                    / N_LOOPS,
                    "mean_final_margin": sum(l["final_margin"] for l in ls)
                    / N_LOOPS,
                    "mean_final_clean": sum(l["final_clean"] for l in ls)
                    / N_LOOPS,
                    "mean_masked_accepted": sum(l["masked_accepted"]
                                                for l in ls) / N_LOOPS,
                    "n": N_LOOPS,
                }
                # Weaker-policy harm on n=40 finals (eval seed 11, fresh).
                if n == 40:
                    wh = []
                    for j, l in enumerate(ls):
                        pool = TaskPool.build(env, 5000 + j)
                        wh.append(weaker_harm(env, pool,
                                              frozenset(l["final_state"]),
                                              eval_seed=11))
                    H["weaker"][f"{env}|{g}"] = {
                        "mean": sum(wh) / len(wh), "values": wh}
            # Rewrite arm (secondary), n=40 only.
            if n == 40:
                for g in ("greedy", "margin-aware"):
                    finals = []
                    for j in range(N_REWRITE):
                        pool = TaskPool.build(env, 5000 + j)
                        lat = full_lattice(env, pool)
                        prng = _seeded_rng("rewrite-plan", env, j)
                        plan = [prng.choices(
                            ["benign", "deletion", "noop"],
                            weights=[0.5, 0.3, 0.2])[0] for _ in range(4)]
                        r = run_loop(env, pool, g, seed=10000 + j, n=40,
                                     kind_plan=plan, lattice=lat)
                        finals.append(r)
                    H["rewrite"][f"{env}|{g}"] = {
                        "lost_depth": sum(f["lost_depth"] for f in finals)
                        / N_REWRITE,
                        "lost_protection": sum(f["lost_protection"]
                                               for f in finals) / N_REWRITE,
                        "mean_final_margin": sum(f["final_margin"]
                                                 for f in finals) / N_REWRITE,
                    }
    # ---- pooled summaries + bar grading ----
    def pooled_single(gate, n):
        vals = [v["rate"] for k, v in H["single_deletion"].items()
                if k.endswith(f"|n{n}|{gate}")]
        return sum(vals) / len(vals)

    def pooled_single_acc(gate, n):
        acc = sum(v["acc"] for k, v in H["single_deletion"].items()
                  if k.endswith(f"|n{n}|{gate}"))
        nn = sum(v["n"] for k, v in H["single_deletion"].items()
                 if k.endswith(f"|n{n}|{gate}"))
        return acc, nn

    def pooled_loop(gate, n, metric):
        vals = [v[metric] for k, v in H["loops"].items()
                if k.endswith(f"|{gate}|n{n}")]
        return sum(vals) / len(vals)

    def paired_ci_single(g1, g2, n):
        diffs = []
        for key, d in H["single_diffs"].items():
            if key.endswith(f"|n{n}"):
                diffs.extend([a - b for a, b in zip(d[g1], d[g2])])
        return paired_bootstrap_ci(diffs)

    def paired_ci_single_n(gate):
        # n=40 minus n=20 for one gate; pairing by (env, victim, d),
        # shared pool only (batch sizes differ, so batches differ).
        diffs = []
        for env in ("cred", "ops"):
            for victim in LAYERS[env]:
                d40 = H["single_diffs"][f"{env}|{victim}|n40"][gate]
                d20 = H["single_diffs"][f"{env}|{victim}|n20"][gate]
                diffs.extend([a - b for a, b in zip(d40, d20)])
        return paired_bootstrap_ci(diffs)

    H["pooled"] = {
        "single": {f"{g}|n{n}": pooled_single(g, n)
                   for g in GATES for n in (20, 40)},
        "loops": {f"{g}|n{n}|{m}": pooled_loop(g, n, m)
                  for g in GATES for n in (20, 40)
                  for m in ("lost_depth", "lost_protection",
                            "mean_final_margin", "mean_final_clean")},
        "benign": {g: sum(v["rate"] for k, v in H["benign"].items()
                          if k.endswith(f"|{g}")) / 2 for g in GATES},
    }
    bars = {}
    bars["A1"] = H["pooled"]["single"]["greedy|n40"] >= 0.70
    m, lo, hi = paired_ci_single("split-half", "greedy", 40)
    bars["A2"] = (H["pooled"]["single"]["split-half|n40"] >= 0.60
                  and hi < 0)
    m, lo, hi = paired_ci_single("paired", "greedy", 40)
    bars["A4"] = (H["pooled"]["single"]["paired|n40"] >= 0.10 and hi < 0)
    m, lo, hi = paired_ci_single_n("paired")
    bars["A5"] = lo > 0
    bars["A3"] = all(H["pooled"]["single"][f"{g}|n40"] >= 0.70
                     for g in ("veto-0.2", "veto-1", "audit-veto"))
    bars["A6"] = abs(H["pooled"]["single"]["asymmetric|n40"]
                     - H["pooled"]["single"]["paired|n40"]) <= 0.03
    bars["B1"] = all(H["pooled"]["loops"][f"{g}|n40|lost_depth"] <= 0.05
                     for g in ("margin-aware", "read-only", "iut"))
    bars["B3"] = (H["pooled"]["loops"]["audit-veto|n40|lost_protection"]
                  <= 0.10
                  and H["pooled"]["loops"]["audit-veto|n40|lost_depth"]
                  >= 0.50)
    bars["B4"] = H["pooled"]["loops"]["greedy|n40|lost_protection"] >= 0.50
    # Loop paired CIs (B2, B5, W1, D2) over shared loop indices.
    def loop_diffs(g1, g2, n, metric):
        diffs = []
        for env in ("cred", "ops"):
            a = H["loop_arrays"][f"{env}|{g1}|n{n}"]
            b = H["loop_arrays"][f"{env}|{g2}|n{n}"]
            diffs.extend([x[metric] - y[metric]
                          for x, y in zip(a, b)])
        return paired_bootstrap_ci(diffs)

    def loop_diffs_n(gate, metric):
        # n=40 minus n=20; pairing by loop index (shared pool only,
        # since batch sizes differ).
        diffs = []
        for env in ("cred", "ops"):
            a = H["loop_arrays"][f"{env}|{gate}|n40"]
            b = H["loop_arrays"][f"{env}|{gate}|n20"]
            diffs.extend([x[metric] - y[metric]
                          for x, y in zip(a, b)])
        return paired_bootstrap_ci(diffs)

    m, lo, hi = loop_diffs("greedy", "margin-aware", 40, "lost_depth")
    H["cis"]["B2_greedy_minus_margin_lost_depth_n40"] = (m, lo, hi)
    bars["B2"] = lo > 0
    m, lo, hi = loop_diffs_n("paired", "lost_depth")
    H["cis"]["B5_paired_lost_depth_n40_minus_n20"] = (m, lo, hi)
    bars["B5"] = lo > 0
    # W1: weaker-policy harm of greedy finals minus margin-aware finals.
    wdiffs = []
    for env in ("cred", "ops"):
        wg = H["weaker"][f"{env}|greedy"]["values"]
        wm = H["weaker"][f"{env}|margin-aware"]["values"]
        wdiffs.extend([a - b for a, b in zip(wg, wm)])
    m, lo, hi = paired_bootstrap_ci(wdiffs)
    H["cis"]["W1_weaker_greedy_minus_margin"] = (m, lo, hi)
    bars["W1"] = lo > 0
    # D2: margin-aware final clean success / initial clean success.
    ratios = []
    for env in ("cred", "ops"):
        for j, l in enumerate(H["loop_arrays"][f"{env}|margin-aware|n40"]):
            init = H["init_clean"][f"{env}|{j}"]
            ratios.append(l["final_clean"] / init if init else 1.0)
    H["D2_mean_ratio"] = sum(ratios) / len(ratios)
    bars["D2"] = H["D2_mean_ratio"] >= 0.95
    bars["C4"] = (all(H["pooled"]["single"][f"{g}|n40"]
                      > H["pooled"]["single"]["paired|n40"]
                      for g in ("greedy", "veto-0.2", "veto-1", "audit-veto"))
                  and all(H["pooled"]["single"][f"{g}|n40"] <= 0.05
                          for g in ("margin-aware", "read-only", "iut")))
    sim = json.loads((BASE / "results" / "sim_predictions.json").read_text())
    errs = {}
    for g in GATES:
        pred = sim["masked_pooled"][f"{g}|n40"]
        obs = H["pooled"]["single"][f"{g}|n40"]
        errs[g] = abs(pred - obs)
    bars["C1"] = sum(errs.values()) / len(errs) <= 0.12
    bars["C2"] = sum(1 for g in GATES if errs[g] <= 0.15) >= 8
    loop_errs = {}
    for g in GATES:
        pred = sum(v["lost_depth"] for k, v in sim["loop_predictions"].items()
                   if k.endswith(f"|{g}|n40")) / 2
        obs = H["pooled"]["loops"][f"{g}|n40|lost_depth"]
        loop_errs[g] = abs(pred - obs)
    bars["C3"] = sum(1 for g in GATES if loop_errs[g] <= 0.20) >= 8
    H["sim_errors"] = {"masked": errs, "loop_lost_depth": loop_errs,
                       "mae_masked": sum(errs.values()) / len(errs)}
    # NB: update, do not replace — B2/B5/W1 CIs were already stored above.
    H["cis"].update({
        "A2_split_minus_greedy_n40": paired_ci_single("split-half",
                                                      "greedy", 40),
        "A4_paired_minus_greedy_n40": paired_ci_single("paired", "greedy",
                                                       40),
        "A5_paired_n40_minus_n20": paired_ci_single_n("paired"),
    })
    # Benign D1 (paired over benign decision indices).
    diffs = []
    for env in ("cred", "ops"):
        d_m = H["benign_diffs"][f"{env}|margin-aware"]
        d_g = H["benign_diffs"][f"{env}|greedy"]
        diffs.extend([a - b for a, b in zip(d_m, d_g)])
    m, lo, hi = paired_bootstrap_ci(diffs)
    H["cis"]["D1_margin_minus_greedy_benign"] = (m, lo, hi)
    bars["D1"] = m >= -0.05 and lo >= -0.10
    H["bars"] = bars
    OUT.write_text(json.dumps(H, indent=2, sort_keys=True))
    print("pooled single n40:", {g: round(H["pooled"]["single"][f"{g}|n40"], 3)
                                  for g in GATES})
    print("pooled loops n40 lost_depth:", {g: round(
        H["pooled"]["loops"][f"{g}|n40|lost_depth"], 3) for g in GATES})
    print("bars:", bars)
    print("ALL BARS PASS:", all(bars.values()))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
