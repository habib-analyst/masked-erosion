"""Unit tests for masked_erosion (stdlib unittest, deterministic)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from masked_erosion import (GATES, TAU, TaskPool, _mcnemar_accept,
                            decide_gate, draw_batch, eval_task, full_lattice,
                            lattice_harm, margin, paired_outcomes, run_loop,
                            weaker_harm, wilson, _seeded_rng)


class TestLattice(unittest.TestCase):
    def test_all_envs_lattice_shape(self):
        for env in ("cred", "ops"):
            pool = TaskPool.build(env, 777)
            lat = full_lattice(env, pool)
            self.assertEqual(len(lat), 16)
            for state, v in lat.items():
                if len(state) == 4:
                    self.assertEqual(v["harm"], 0.0)
                    self.assertEqual(v["margin"], 2)
                elif len(state) == 3:
                    self.assertEqual(v["harm"], 0.0)
                    self.assertEqual(v["margin"], 1)
                elif len(state) == 2:
                    self.assertGreater(v["harm"], TAU)
                    self.assertEqual(v["margin"], 0)
                elif len(state) <= 1:
                    self.assertGreater(v["harm"], TAU)
                    self.assertEqual(v["margin"], 0)

    def test_masked_deletion_zero_child_only_harm(self):
        for env in ("cred", "ops"):
            pool = TaskPool.build(env, 778)
            from masked_erosion import LAYERS
            full = frozenset(LAYERS[env])
            for victim in LAYERS[env]:
                child = full - {victim}
                h01 = sum(1 for t in pool.harm
                          if eval_task(env, child, t)[1]
                          and not eval_task(env, full, t)[1]) / len(pool.harm)
                self.assertEqual(h01, 0.0)
                self.assertEqual(
                    lattice_harm(env, pool, child)
                    - lattice_harm(env, pool, full), 0.0)

    def test_weaker_policy_harm_rises_after_masked_deletion(self):
        for env in ("cred", "ops"):
            pool = TaskPool.build(env, 779)
            from masked_erosion import LAYERS
            full = frozenset(LAYERS[env])
            h0 = weaker_harm(env, pool, full, eval_seed=5)
            child_harms = [weaker_harm(env, pool, full - {v}, eval_seed=5)
                           for v in LAYERS[env]]
            self.assertGreater(sum(child_harms) / len(child_harms), h0)
            self.assertGreater(h0, 0.0)  # noisy blocks leak even at full stack


class TestGates(unittest.TestCase):
    def test_mcnemar_boundary(self):
        # n01 = 5, n10 = 0 -> p = 1/32 <= .05 accept; n01 = 4 -> reject.
        self.assertTrue(_mcnemar_accept([(False, True, False)] * 5))
        self.assertFalse(_mcnemar_accept([(False, True, False)] * 4))
        self.assertFalse(_mcnemar_accept([]))
        self.assertFalse(_mcnemar_accept([(True, True, False)] * 10))

    def test_greedy_tie_rejects(self):
        rows = [(True, True, False)] * 10
        self.assertFalse(_mcnemar_accept(rows))
        from masked_erosion import _greedy
        self.assertFalse(_greedy(rows))

    def test_read_only_rejects_deletions(self):
        pool = TaskPool.build("cred", 780)
        from masked_erosion import LAYERS
        full = frozenset(LAYERS[env]) if False else frozenset(LAYERS["cred"])
        child = full - {"auth"}
        rng = _seeded_rng("t", 1)
        batch = draw_batch(pool, rng, 40)
        rows = paired_outcomes("cred", full, child, batch)
        self.assertFalse(decide_gate("read-only", "cred", pool, full, child,
                                     batch, rows, rng, kind="deletion"))

    def test_margin_aware_rejects_masked_accepts_benign(self):
        pool = TaskPool.build("cred", 781)
        from masked_erosion import LAYERS
        full = frozenset(LAYERS["cred"])
        child = full - {"auth"}
        rng = _seeded_rng("t", 2)
        batch = draw_batch(pool, rng, 40)
        rows = paired_outcomes("cred", full, child, batch)
        # Force a greedy win so the margin condition is the deciding factor.
        rows = [(False, True, False)] * 6 + rows[6:]
        self.assertFalse(decide_gate("margin-aware", "cred", pool, full,
                                     child, batch, rows, rng,
                                     kind="deletion"))
        rows_b = paired_outcomes("cred", full, full, batch, kind="benign")
        rows_b = [(False, True, False)] * 6 + rows_b[6:]
        self.assertTrue(decide_gate("margin-aware", "cred", pool, full,
                                    full, batch, rows_b, rng, kind="benign"))

    def test_all_gates_return_bool(self):
        pool = TaskPool.build("ops", 782)
        from masked_erosion import LAYERS
        full = frozenset(LAYERS["ops"])
        child = full - {"scope"}
        rng = _seeded_rng("t", 3)
        batch = draw_batch(pool, rng, 40)
        rows = paired_outcomes("ops", full, child, batch)
        for g in GATES:
            r = decide_gate(g, "ops", pool, full, child, batch, rows, rng,
                            kind="deletion")
            self.assertIsInstance(r, bool, g)


class TestDeterminism(unittest.TestCase):
    def test_loop_byte_identical(self):
        pool = TaskPool.build("cred", 783)
        a = run_loop("cred", pool, "greedy", seed=11, n=40)
        b = run_loop("cred", pool, "greedy", seed=11, n=40)
        self.assertEqual(a, b)
        pool2 = TaskPool.build("cred", 783)
        c = run_loop("cred", pool2, "greedy", seed=11, n=40)
        self.assertEqual(a, c)


class TestStats(unittest.TestCase):
    def test_wilson_zero(self):
        lo, hi = wilson(0, 100)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.05)


if __name__ == "__main__":
    unittest.main()
