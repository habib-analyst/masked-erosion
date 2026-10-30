"""Pilot run (pilot seeds 1000-1009): lattice, single-deletion acceptance,
batch-size sweep, weaker-policy arm, benign-edit acceptance.

Informs PREREG design only. Head-to-head uses FRESH seeds (5000+), so no
pilot number is ever reported as a confirmatory result.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masked_erosion import (GATES, LAYERS, TaskPool, _seeded_rng, decide_gate,
                            draw_batch, full_lattice, lattice_harm,
                            paired_outcomes, weaker_harm, wilson)

OUT = Path(__file__).resolve().parent / "results" / "pilot.json"
N_DECISIONS = 400  # per (env, edge, n)


def main():
    res = {"lattice": {}, "single_deletion": {}, "weaker": {},
           "benign": {}, "batch_sweep": {}}
    for env in ("cred", "ops"):
        pool = TaskPool.build(env, 1000)
        lat = full_lattice(env, pool)
        res["lattice"][env] = {",".join(k) if k else "(empty)": v
                               for k, v in lat.items()}
        full = frozenset(LAYERS[env])
        # Weaker-policy harm by state size (eval seed fixed for pilot).
        res["weaker"][env] = {
            "full": weaker_harm(env, pool, full, eval_seed=7),
            "size3_mean": sum(weaker_harm(env, pool, full - {v}, eval_seed=7)
                              for v in LAYERS[env]) / 4,
            "size2_mean": sum(
                weaker_harm(env, pool, frozenset(c), eval_seed=7)
                for c in [tuple(sorted(full - {a, b}))
                          for i, a in enumerate(LAYERS[env])
                          for b in LAYERS[env][i + 1:]]) / 6,
            "empty": weaker_harm(env, pool, frozenset(), eval_seed=7),
        }
        for n in (20, 40):
            for victim in LAYERS[env]:
                child = full - {victim}
                for gate in GATES:
                    acc = 0
                    for d in range(N_DECISIONS):
                        rng = _seeded_rng("pilot-dec", env, victim, n, d)
                        batch = draw_batch(pool, rng, n)
                        rows = paired_outcomes(env, full, child, batch)
                        if decide_gate(gate, env, pool, full, child, batch,
                                       rows, rng, kind="deletion"):
                            acc += 1
                    key = f"{env}|{victim}|n{n}|{gate}"
                    lo, hi = wilson(acc, N_DECISIONS)
                    res["single_deletion"][key] = {
                        "acc": acc, "n": N_DECISIONS,
                        "rate": acc / N_DECISIONS, "wilson": [lo, hi]}
            # Benign-edit acceptance at n=40.
            for gate in GATES:
                acc = 0
                for d in range(N_DECISIONS):
                    rng = _seeded_rng("pilot-ben", env, n, d)
                    batch = draw_batch(pool, rng, 40)
                    rows = paired_outcomes(env, full, full, batch,
                                           kind="benign")
                    if decide_gate(gate, env, pool, full, full, batch, rows,
                                   rng, kind="benign"):
                        acc += 1
                lo, hi = wilson(acc, N_DECISIONS)
                res["benign"][f"{env}|{gate}"] = {
                    "acc": acc, "n": N_DECISIONS,
                    "rate": acc / N_DECISIONS, "wilson": [lo, hi]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, sort_keys=True))
    # Pilot-gate summary to stdout.
    for env in ("cred", "ops"):
        lat = res["lattice"][env]
        print(env, "H0 margin:", lat[",".join(sorted(LAYERS[env]))]["margin"],
              "size3 harm:", sorted({v["harm"] for k, v in lat.items()
                                      if len(k.split(",")) == 3}),
              "weaker:", res["weaker"][env])
    for n in (20, 40):
        for gate in ("greedy", "paired", "margin-aware", "veto-1",
                     "audit-veto"):
            rates = [v["rate"] for k, v in res["single_deletion"].items()
                     if k.endswith(f"|n{n}|{gate}")]
            print(f"n={n} {gate} masked-accept mean over envs/edges:",
                  round(sum(rates) / len(rates), 3))
    print("benign acceptance (mean over envs):")
    for gate in GATES:
        rates = [v["rate"] for k, v in res["benign"].items()
                 if k.endswith(f"|{gate}")]
        print(" ", gate, round(sum(rates) / len(rates), 3))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
