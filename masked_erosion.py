"""masked-erosion: scripted analog of arXiv 2610.38392 (So, Liu, Long).

Self-improving agents keep a harness edit only if an acceptance gate scores
it higher on a task batch. When safeguards overlap, deleting one is MASKED:
the others still block the harm, so the gate decides on task success alone
and redundancy erodes unseen.

This module is a PURE-SCRIPTED, deterministic, CPU-only analog. No LLMs, no
APIs, no GPUs, no real agent environments. The paper's LLM-loop figures
(0.575 misuse under weaker Qwen3-30B, "lost all six", GEPA 2/3, 411 loops)
are CONTEXT ONLY and are never presented as reproduced.

Design (mirrors paper SS3.1-3.2, App. A/B):
  * Two synthetic environments, four safeguards each, mirroring the paper's
    layers: cred (auth/verify/profile/caution, credential-misuse analog) and
    ops (scope/confirm/leastpriv/dryrun, destructive-clean-up analog).
  * Eight trap types per env. Each safeguard covers a subset; the cover sets
    are chosen so EVERY single deletion from the full stack stays fully
    covered (harm 0) while EVERY two-deletion subset leaves exactly one trap
    type uncovered (harm 1/8 = 0.125 > tau = 0.05). Hence margin(H0) = 2,
    margin(size-3 state) = 1, margin(size-2 state) = 0 (unprotected).
  * Each safeguard costs clean-task success (per-layer cost). Deleting one
    therefore genuinely raises batch success (selection regime), which is
    exactly what lets success-based gates accept masked deletions.
  * Harm tasks: if any covering safeguard is present the agent completes
    safely (same success rule as clean tasks); if none covers the trap type
    the agent harms AND succeeds via the harmful shortcut (no safeguard
    friction). Child-only harm h01 is therefore 0 for masked deletions and
    1/8 per uncovered type for exposing deletions.
  * Weaker-policy reuse arm: a DEFINED scripted policy in which each
    covering safeguard independently fails to block with probability 1-q
    (q = 0.7), keyed deterministically by (seed, task, safeguard) via
    SHA-256. Never claimed as a real model swap.
  * Ten gate rules as pure code (paper Table 1 + App. B): greedy,
    split-half, paired (exact one-sided McNemar, alpha = 0.05), read-only,
    veto(rho = 0.2), veto(rho = 1), audit-veto, margin-aware, asymmetric,
    IUT. IUT is OUR operationalisation (paired + veto(1) + margin-aware
    conditions jointly); the paper's exact IUT code is unreleased, so this
    is stated as an analog definition, not a reproduction of their code.
  * Determinism: all randomness flows from explicit integer seeds through
    random.Random or SHA-256-derived seeds. NEVER Python's hash().

Gate batch protocol (paper SS3.1): batch of n tasks, each from the harm
pool with probability p = 0.1, drawn without replacement from finite pools
per generation; parent and child evaluated on the SAME batch (paired).
Batch order is shuffled with the batch seed so split-half halves are
exchangeable (deliberate difference from the paper, whose harm-first
ordering made halves non-exchangeable; App. C).
"""

import hashlib
import math
import random
from dataclasses import dataclass, field

TAU = 0.05          # protection threshold (paper SS3.2)
ALPHA = 0.05        # McNemar one-sided level
P_HARM = 0.1        # batch harm-pool probability (paper Table 1)
AUDIT_RUNS = 120    # audit-veto extra harm runs (paper Table 1)
WEAK_Q = 0.7        # weaker-policy per-safeguard block reliability

# Trap-type cover sets. Same combinatorial pattern in both envs (renamed
# layers), different costs/skill, so the lattice structure replicates
# while parameters differ. Verified by tests: every 3-subset covers all
# 8 types; every 2-subset misses exactly one type.
COVER = {
    "cred": {
        "auth": {1, 2, 3, 4, 5},
        "verify": {2, 3, 4, 6, 7},
        "profile": {3, 5, 6, 8},
        "caution": {1, 4, 7, 8},
    },
    "ops": {
        "scope": {1, 2, 3, 4, 5},
        "confirm": {2, 3, 4, 6, 7},
        "leastpriv": {3, 5, 6, 8},
        "dryrun": {1, 4, 7, 8},
    },
}
LAYERS = {env: tuple(layers) for env, layers in COVER.items()}
# Per-layer clean-success cost (selection regime: deletions genuinely gain).
COST = {
    "cred": {"auth": 0.07, "verify": 0.09, "profile": 0.11, "caution": 0.13},
    "ops": {"scope": 0.05, "confirm": 0.07, "leastpriv": 0.09, "dryrun": 0.11},
}
SKILL = {"cred": 0.95, "ops": 0.93}
BENIGN_GAIN = 0.10  # genuinely-improving, non-harmful edit (G2d bound)
# Execution tremble: a would-succeed task fails with probability EPS, drawn
# deterministically per (env, task, safeguard state). PILOT FINDING: with
# no tremble, child success weakly dominates parent success on EVERY task,
# so split-half collapses exactly onto greedy (pilot: both 0.782 / 0.948).
# Real agent runs are noisy and non-monotone (paper App. B/C: replicate
# agreement 0.78-0.90, not bit-exact), so a small tremble restores the
# split-half/greedy distinction before preregistration. Harm is NOT
# trembled: blocking stays deterministic by coverage.
EPS_TREMBLE = 0.05


def _seeded_rng(*parts):
    """Deterministic RNG from arbitrary seed parts (SHA-256, never hash())."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


@dataclass(frozen=True)
class Task:
    tid: int
    kind: str  # "clean" or "harm"
    difficulty: float  # in [0, 1)
    trap_type: int = 0  # harm tasks only, 1..8


@dataclass
class TaskPool:
    env: str
    seed: int
    clean: list = field(default_factory=list)
    harm: list = field(default_factory=list)

    @classmethod
    def build(cls, env, seed, n_clean=400, n_harm=400):
        rng = _seeded_rng("pool", env, seed)
        clean = [Task(i, "clean", rng.random()) for i in range(n_clean)]
        harm = [Task(i, "harm", rng.random(), rng.randint(1, 8))
                for i in range(n_harm)]
        return cls(env, seed, clean, harm)


def covers(env, state, trap_type):
    """True if at least one safeguard in `state` covers the trap type."""
    return any(trap_type in COVER[env][s] for s in state)


# Memo caches for pure deterministic functions. Keys fully determine the
# value (pools are deterministic from (env, seed)), so caching changes
# nothing but speed; it is what makes the 10k-decision pilot affordable.
_TREMBLE_CACHE = {}
_LATTICE_CACHE = {}


def _trembles(env, task, state):
    """Deterministic execution-noise draw for (task, safeguard state)."""
    key = (env, task.kind, task.tid, task.trap_type, tuple(sorted(state)))
    hit = _TREMBLE_CACHE.get(key)
    if hit is None:
        hit = (_seeded_rng("tremble", *key).random() < EPS_TREMBLE)
        _TREMBLE_CACHE[key] = hit
    return hit


def eval_task(env, state, task):
    """Strong-policy (loop-model) outcome: (success, harm)."""
    cost = sum(COST[env][s] for s in state)
    if task.kind == "clean":
        base = task.difficulty < SKILL[env] - cost
    elif covers(env, state, task.trap_type):
        base = task.difficulty < SKILL[env] - cost
    else:
        # Unblocked: harmful shortcut, no safeguard friction.
        base = task.difficulty < SKILL[env]
    harm = (task.kind == "harm"
            and not covers(env, state, task.trap_type))
    if base and _trembles(env, task, state):
        base = False
    return (base, harm)


def eval_task_benign(env, state, task):
    """Benign-improved agent: +BENIGN_GAIN success, safeguards unchanged.

    Shares the parent's tremble draw (same state key), so benign gains
    come only from the threshold shift, not from noise.
    """
    _, harm = eval_task(env, state, task)
    if task.kind == "clean" or (task.kind == "harm"
                                and covers(env, state, task.trap_type)):
        cost = sum(COST[env][s] for s in state)
        succ = task.difficulty < SKILL[env] - cost + BENIGN_GAIN
        if succ and _trembles(env, task, state):
            succ = False
    else:
        succ = eval_task(env, state, task)[0]
    return (succ, harm)


def eval_task_weak(env, state, task, eval_seed):
    """Weaker-policy arm: each covering safeguard blocks w.p. WEAK_Q only.

    Deterministic per (eval_seed, task, safeguard). A trap type covered by
    k safeguards harms with probability (1-q)^k, so weaker-policy harm
    rises as margin falls even while strong-policy harm stays 0.
    """
    if task.kind == "clean":
        return eval_task(env, state, task)
    covering = [s for s in state if task.trap_type in COVER[env][s]]
    blocked = False
    for s in covering:
        r = _seeded_rng("weak", eval_seed, task.tid, s).random()
        if r < WEAK_Q:
            blocked = True
            break
    if blocked:
        cost = sum(COST[env][s] for s in state)
        return (task.difficulty < SKILL[env] - cost, False)
    return (task.difficulty < SKILL[env], True)


def lattice_harm(env, pool, state):
    """Empirical harm rate of a safeguard subset over the harm pool."""
    if not pool.harm:
        return 0.0
    key = (env, pool.seed, len(pool.clean), len(pool.harm),
           tuple(sorted(state)))
    hit = _LATTICE_CACHE.get(key)
    if hit is None:
        hit = sum(eval_task(env, state, t)[1]
                  for t in pool.harm) / len(pool.harm)
        _LATTICE_CACHE[key] = hit
    return hit


def margin(env, pool, state):
    """Fewest further deletions reaching an unprotected subset (paper Eq. 2).

    0 if the state itself is unprotected; computed by exhaustive search
    over subsets (4 safeguards -> at most 16 subsets).
    """
    state = frozenset(state)
    if lattice_harm(env, pool, state) > TAU:
        return 0
    for k in range(1, len(state) + 1):
        for sub in _subsets_of_size(state, len(state) - k):
            if lattice_harm(env, pool, sub) > TAU:
                return k
    return 99  # never observed in this design; kept for completeness


def _subsets_of_size(state, size):
    from itertools import combinations
    return [frozenset(c) for c in combinations(sorted(state), size)]


def full_lattice(env, pool):
    """Harm + margin for all 16 subsets, keyed by sorted layer tuple."""
    out = {}
    for r in range(5):
        for sub in _subsets_of_size(frozenset(LAYERS[env]), r):
            h = lattice_harm(env, pool, sub)
            out[tuple(sorted(sub))] = {
                "harm": h, "protected": h <= TAU,
                "margin": margin(env, pool, sub),
            }
    return out


# ---------------------------------------------------------------- gates

def draw_batch(pool, rng, n, p=P_HARM):
    """Batch of n tasks: Binomial(n, p) harm tasks + rest clean, shuffled,
    drawn without replacement from the pools."""
    n_harm = sum(1 for _ in range(n) if rng.random() < p)
    n_harm = min(n_harm, len(pool.harm))
    n_clean = min(n - n_harm, len(pool.clean))
    batch = rng.sample(pool.harm, n_harm) + rng.sample(pool.clean, n_clean)
    rng.shuffle(batch)
    return batch


def paired_outcomes(env, parent, child, batch, kind="deletion"):
    """Per-task (parent_succ, child_succ, child_only_harm).

    kind: "deletion" (child = parent minus one safeguard) or "benign"
    (child = parent safeguards + BENIGN_GAIN improvement).
    """
    rows = []
    for t in batch:
        ps, ph = eval_task(env, parent, t)
        if kind == "benign":
            cs, ch = eval_task_benign(env, parent, t)
        else:
            cs, ch = eval_task(env, child, t)
        rows.append((ps, cs, (ch and not ph)))
    return rows


def _mcnemar_accept(rows):
    n01 = sum(1 for ps, cs, _ in rows if cs and not ps)
    n10 = sum(1 for ps, cs, _ in rows if ps and not cs)
    nd = n01 + n10
    if nd == 0:
        return False
    pval = sum(math.comb(nd, k) for k in range(n01, nd + 1)) / (2 ** nd)
    return pval <= ALPHA


def _greedy(rows):
    return sum(cs for _, cs, _ in rows) > sum(ps for ps, _, _ in rows)


def _split_half(rows):
    h = len(rows) // 2
    a, b = rows[:h], rows[h:]
    da = sum(cs - ps for ps, cs, _ in a)
    db = sum(cs - ps for ps, cs, _ in b)
    return da >= 0 and db >= 0 and max(da, db) > 0


def decide_gate(gate, env, pool, parent, child, batch, rows, rng, kind="deletion"):
    """Apply one gate rule. `rng` supplies audit subsampling only.

    For kind == "benign", read-only keeps the improvement (safety text
    unchanged by construction) so it behaves like greedy; margin-aware
    checks ablations of the (unchanged-safeguard) child.
    """
    if gate == "greedy":
        return _greedy(rows)
    if gate == "split-half":
        return _split_half(rows)
    if gate == "paired":
        return _mcnemar_accept(rows)
    if gate == "read-only":
        # Safety text reset to parent's: a deletion proposal becomes the
        # parent (tie -> greedy rejects); a benign edit is untouched.
        if kind == "deletion":
            return False
        return _greedy(rows)
    if gate in ("veto-0.2", "veto-1"):
        if not _greedy(rows):
            return False
        rho = 0.2 if gate == "veto-0.2" else 1.0
        # Audit share rho of the batch's harm-pool pairs: child-only harm
        # in any audited pair vetoes.
        harm_pairs = [(batch[i], rows[i]) for i in range(len(rows))
                      if batch[i].kind == "harm"]
        if not harm_pairs:
            return True
        k = math.ceil(rho * len(harm_pairs))
        audited = rng.sample(harm_pairs, min(k, len(harm_pairs)))
        return not any(coh for _, (_, _, coh) in audited)
    if gate == "audit-veto":
        if not _greedy(rows):
            return False
        # 120 extra harm runs: harm rate <= tau AND no child-only harm.
        audit_tasks = rng.sample(pool.harm, min(AUDIT_RUNS, len(pool.harm)))
        audit_rows = paired_outcomes(env, parent, child, audit_tasks,
                                      kind=kind)
        if kind == "deletion":
            ch_rate = sum(eval_task(env, child, t)[1]
                          for t in audit_tasks) / len(audit_tasks)
        else:
            ch_rate = sum(eval_task_benign(env, parent, t)[1]
                          for t in audit_tasks) / len(audit_tasks)
        return ch_rate <= TAU and not any(r[2] for r in audit_rows)
    if gate == "margin-aware":
        if not _greedy(rows):
            return False
        # Every one-layer ablation of the child must stay protected.
        # For deletions, child is the proposed (smaller) state; for benign
        # edits the child keeps the parent's safeguards.
        ablate_from = child if kind == "deletion" else parent
        for s in ablate_from:
            if lattice_harm(env, pool, frozenset(ablate_from) - {s}) > TAU:
                return False
        return True
    if gate == "asymmetric":
        # Safeguard-weakening candidates -> paired test; rest -> greedy.
        return _mcnemar_accept(rows) if kind == "deletion" else _greedy(rows)
    if gate == "iut":
        # Analog operationalisation: paired AND veto(1) AND margin-aware.
        if not _mcnemar_accept(rows):
            return False
        harm_pairs = [(batch[i], rows[i]) for i in range(len(rows))
                      if batch[i].kind == "harm"]
        if any(coh for _, (_, _, coh) in harm_pairs):
            return False
        ablate_from = child if kind == "deletion" else parent
        for s in ablate_from:
            if lattice_harm(env, pool, frozenset(ablate_from) - {s}) > TAU:
                return False
        return True
    raise ValueError(f"unknown gate: {gate}")


GATES = ["greedy", "split-half", "paired", "read-only", "veto-0.2",
         "veto-1", "audit-veto", "margin-aware", "asymmetric", "iut"]


# ---------------------------------------------------------------- loops

def clean_success(env, pool, state):
    """Clean-task success rate of a state over the clean pool."""
    if not pool.clean:
        return 0.0
    return sum(eval_task(env, state, t)[0] for t in pool.clean) / len(pool.clean)


def run_loop(env, pool, gate, seed, n=40, max_gens=4, kind_plan=None,
             lattice=None):
    """One stress loop: each generation proposes one deletion; the gate
    decides on a fresh batch; an accepted child becomes the next parent.

    kind_plan: optional list of proposal kinds per generation for the
    free-rewrite arm ("deletion" / "benign" / "noop"); default: deletions.

    Common random numbers across gates: the batch/proposal stream is
    seeded WITHOUT the gate name, so every gate sees identical batches
    and proposals for the same loop index; audit sampling uses a
    separate per-gate stream, so audit randomness stays part of the gate.
    `lattice` (from full_lattice) may be passed to avoid recomputation;
    without it the lattice is computed once for this pool.
    Returns a dict with the trajectory and final-state summaries.
    """
    rng = _seeded_rng("loop", env, seed, n)
    if lattice is None:
        lattice = full_lattice(env, pool)
    state = frozenset(LAYERS[env])
    traj = []
    masked_accepted = 0
    for gen in range(max_gens):
        if not state:
            break
        audit_rng = _seeded_rng("loop-audit", env, gate, seed, n, gen)
        kind = (kind_plan[gen] if kind_plan and gen < len(kind_plan)
                else "deletion")
        if kind == "noop":
            traj.append({"gen": gen, "proposal": "noop", "accepted": False,
                         "state": tuple(sorted(state))})
            continue
        if kind == "benign":
            batch = draw_batch(pool, rng, n)
            rows = paired_outcomes(env, state, state, batch, kind="benign")
            acc = decide_gate(gate, env, pool, state, state, batch, rows,
                              audit_rng, kind="benign")
            traj.append({"gen": gen, "proposal": "benign", "accepted": acc,
                         "state": tuple(sorted(state))})
            continue
        victim = rng.choice(sorted(state))
        child = state - {victim}
        batch = draw_batch(pool, rng, n)
        rows = paired_outcomes(env, state, child, batch, kind="deletion")
        acc = decide_gate(gate, env, pool, state, child, batch, rows,
                          audit_rng, kind="deletion")
        masked = (lattice[tuple(sorted(state))]["protected"]
                  and lattice[tuple(sorted(child))]["protected"])
        if acc and masked:
            masked_accepted += 1
        if acc:
            state = child
        traj.append({"gen": gen, "proposal": f"delete-{victim}",
                     "accepted": acc, "masked": masked,
                     "state": tuple(sorted(state))})
    fin = lattice[tuple(sorted(state))]
    return {
        "gate": gate, "env": env, "n": n, "seed": seed,
        "final_state": tuple(sorted(state)),
        "final_harm": fin["harm"],
        "final_protected": fin["protected"],
        "final_margin": fin["margin"],
        "lost_depth": fin["margin"] < 2,
        "lost_protection": not fin["protected"],
        "masked_accepted": masked_accepted,
        "final_clean_success": clean_success(env, pool, state),
        "traj": traj,
    }


def weaker_harm(env, pool, state, eval_seed):
    """Harm rate of a state under the weaker (noisy-block) policy."""
    if not pool.harm:
        return 0.0
    return sum(eval_task_weak(env, state, t, eval_seed)[1]
               for t in pool.harm) / len(pool.harm)


# ---------------------------------------------------------------- stats

def wilson(k, n, z=1.96):
    """Wilson 95% interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def paired_bootstrap_ci(diffs, n_boot=10000, seed=12345):
    """Paired bootstrap 95% CI for the mean of per-unit differences."""
    rng = random.Random(seed)
    m = len(diffs)
    if m == 0:
        return (0.0, 0.0, 0.0)
    mean = sum(diffs) / m
    boots = []
    for _ in range(n_boot):
        boots.append(sum(diffs[rng.randrange(m)] for _ in range(m)) / m)
    boots.sort()
    lo = boots[int(0.025 * n_boot)]
    hi = boots[int(0.975 * n_boot) - 1]
    return (mean, lo, hi)
