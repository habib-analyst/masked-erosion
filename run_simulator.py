"""Frozen gate simulator (paper SS3.3/App. B analog).

Fit ONLY on calibration pools (seed 2000, never pilot 1000 nor head-to-head
5000+). For each directed lattice edge it resamples calibration-pool tasks
with replacement (bootstrap; the paper uses a Bayesian bootstrap with
Dirichlet weights — uniform resampling is our documented simplification),
applies the EXACT gate code, and chains the per-edge rates over the lattice
to predict loop outcomes. Predictions are frozen into
results/sim_predictions.json BEFORE any head-to-head run; PREREG.md records
its SHA-256. The simulator never sees head-to-head data.
"""
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masked_erosion import (GATES, LAYERS, TAU, TaskPool, _seeded_rng,
                            decide_gate, full_lattice, paired_outcomes)

OUT = Path(__file__).resolve().parent / "results" / "sim_predictions.json"
N_SIM = 1000


def sim_batch(pool, rng, n, p=0.1):
    batch = []
    for _ in range(n):
        if rng.random() < p:
            batch.append(rng.choice(pool.harm))
        else:
            batch.append(rng.choice(pool.clean))
    rng.shuffle(batch)
    return batch


def main():
    preds = {"edge_rates": {}, "loop_predictions": {}, "masked_pooled": {}}
    for env in ("cred", "ops"):
        pool = TaskPool.build(env, 2000)
        lat = full_lattice(env, pool)
        edges = []  # (parent_tuple, victim)
        for r in range(1, 5):
            for parent in itertools.combinations(sorted(LAYERS[env]), r):
                for victim in parent:
                    edges.append((parent, victim))
        for n in (20, 40):
            for parent, victim in edges:
                pstate = frozenset(parent)
                cstate = pstate - {victim}
                counts = {g: 0 for g in GATES}
                for rep in range(N_SIM):
                    rng = _seeded_rng("sim", env, parent, victim, n, rep)
                    batch = sim_batch(pool, rng, n)
                    rows = paired_outcomes(env, pstate, cstate, batch)
                    for g in GATES:
                        audit_rng = _seeded_rng("sim-audit", g, env, parent,
                                                victim, n, rep)
                        if decide_gate(g, env, pool, pstate, cstate, batch,
                                       rows, audit_rng, kind="deletion"):
                            counts[g] += 1
                key = f"{env}|{','.join(parent)}|-{victim}|n{n}"
                preds["edge_rates"][key] = {g: counts[g] / N_SIM
                                            for g in GATES}
            # Chain per-edge rates into loop predictions (4 generations).
            for g in GATES:
                dist = {tuple(sorted(LAYERS[env])): 1.0}
                for _ in range(4):
                    nxt = {}
                    for state, prob in dist.items():
                        if not state:
                            nxt[state] = nxt.get(state, 0.0) + prob
                            continue
                        for victim in state:
                            parent = ",".join(state)
                            rate = preds["edge_rates"][
                                f"{env}|{parent}|-{victim}|n{n}"][g]
                            child = tuple(s for s in state if s != victim)
                            nxt[child] = (nxt.get(child, 0.0)
                                          + prob * rate / len(state))
                            nxt[state] = (nxt.get(state, 0.0)
                                          + prob * (1 - rate) / len(state))
                    dist = nxt
                lost_depth = sum(p for s, p in dist.items()
                                 if lat[s]["margin"] < 2)
                lost_prot = sum(p for s, p in dist.items()
                                if not lat[s]["protected"])
                mean_margin = sum(p * lat[s]["margin"]
                                  for s, p in dist.items())
                preds["loop_predictions"][f"{env}|{g}|n{n}"] = {
                    "lost_depth": lost_depth, "lost_protection": lost_prot,
                    "mean_final_margin": mean_margin}
    # Pooled masked-edge predictions (H0 edges only, both envs).
    for n in (20, 40):
        for g in GATES:
            rates = [v[g] for k, v in preds["edge_rates"].items()
                     if k.endswith(f"|n{n}") and len(k.split("|")[1].split(","))
                     == 4]
            preds["masked_pooled"][f"{g}|n{n}"] = sum(rates) / len(rates)
    OUT.write_text(json.dumps(preds, indent=2, sort_keys=True))
    print("masked pooled predictions:")
    for n in (20, 40):
        print(f" n={n}:", {g: round(preds["masked_pooled"][f"{g}|n{n}"], 3)
                           for g in GATES})
    print("loop lost-depth predictions (mean over envs):")
    for n in (20, 40):
        for g in GATES:
            vals = [v["lost_depth"] for k, v in preds["loop_predictions"].items()
                    if k.endswith(f"|{g}|n{n}")]
            print(f"  n={n} {g}: {sum(vals)/len(vals):.3f}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
