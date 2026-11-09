"""Curve-local solver reuse must preserve results and validation behavior."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd

from BLEs import BLE_JSCwhipple as jsc
from BLEs import BLE_JSCwhipple_mod as modified
from BLEs import BLE_reimerdeswhipple as reimerdes
from BLEs.solver_utils import SolverError, solve_once

ROOT = Path(__file__).resolve().parents[2]
MODELS = [
    (jsc, jsc.JSCwhipple_performance),
    (modified, modified.modJSCwhipple_performance),
    (reimerdes, reimerdes.reimerdes_performance),
]


class SolverReuseTests(unittest.TestCase):
    def test_cache_keys_include_solver_and_every_argument(self):
        cache = {}
        first = Mock(return_value=1.)
        second = Mock(return_value=2.)
        self.assertEqual(solve_once(cache, first, 1., 2.), 1.)
        self.assertEqual(solve_once(cache, first, 1., 2.), 1.)
        first.assert_called_once_with(1., 2.)
        solve_once(cache, first, 2., 2.)
        solve_once(cache, first, 1., 3.)
        self.assertEqual(first.call_count, 3)
        self.assertEqual(solve_once(cache, second, 1., 2.), 2.)
        second.assert_called_once_with(1., 2.)

    def test_failures_are_not_cached(self):
        cache = {}
        solver = Mock(side_effect=[SolverError("did not converge"), 2.])
        with self.assertRaisesRegex(SolverError, "did not converge"):
            solve_once(cache, solver, 1.)
        self.assertEqual(cache, {})
        self.assertEqual(solve_once(cache, solver, 1.), 2.)
        self.assertEqual(solve_once(cache, solver, 1.), 2.)
        self.assertEqual(solver.call_count, 2)

    def test_reuse_is_opt_in_and_local_to_each_curve(self):
        solver = Mock(return_value=2.)
        solve_once(None, solver, 1.)
        solve_once(None, solver, 1.)
        solve_once({}, solver, 1.)
        solve_once({}, solver, 1.)
        self.assertEqual(solver.call_count, 4)


class CurveReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads((ROOT/"validation/tests/fixtures/whipple_solver_baseline.json").read_text())["base_inputs"]

    def test_full_curves_are_identical_with_fewer_solves(self):
        velocities = np.linspace(.1, 15., 150)
        for module, fn in MODELS:
            for angle, ad, s_mli in [(0., 0., 0.), (45., .05, 0.), (65., .05, 1.)]:
                with self.subTest(model=fn.__name__, angle=angle, AD_MLI=ad, S_MLI=s_mli):
                    row = dict(self.base, angle=angle, AD_MLI=ad, S_MLI=s_mli)
                    frame = pd.DataFrame([row]*len(velocities))
                    frame["velocity"] = velocities
                    expected = frame.apply(fn, axis=1).to_numpy()
                    cache = {}
                    transition_name = "vLV_solve_reim" if module is reimerdes else "vLV_solve_piek"
                    with (
                        patch.object(module, transition_name, wraps=getattr(module, transition_name)) as transition,
                        patch.object(module, "dc_HV", wraps=module.dc_HV) as high,
                    ):
                        actual = frame.apply(fn, axis=1, solver_cache=cache).to_numpy()
                    np.testing.assert_array_equal(actual, expected)

                    radians = np.deg2rad(angle)
                    v_hv = 7./np.cos(radians)
                    if s_mli:
                        v_lv = 2./np.cos(radians)
                    elif module in [jsc, modified]:
                        v_lv = 2.6/np.cos(radians)
                    else:
                        tb = row["bumper_thick"]+3*ad/2.78
                        v_lv = module.vLV_solve_reim(tb, row["wall_thick"], row["proj_density"])/np.cos(radians)
                    shatter = np.any((velocities > v_lv) & (velocities < v_hv))
                    # One transition solve, one shatter endpoint solve, plus
                    # the velocity-dependent high-speed solves that remain.
                    self.assertEqual(transition.call_count, int(not s_mli))
                    self.assertEqual(high.call_count, int(shatter)+np.count_nonzero(velocities >= v_hv))
                    self.assertLessEqual(len(cache), 2)

    def test_changed_configurations_do_not_use_stale_results(self):
        changes = [
            {}, {"angle": 45.}, {"bumper_thick": .12},
            {"wall_thick": .25}, {"wall_yield": 60.},
            {"proj_density": 2.8}, {"bumper_density": 2.8},
            {"standoff": 12.}, {"AD_MLI": .05},
            {"AD_MLI": .05, "S_MLI": 1.},
            {"AD_MLI": .1, "S_MLI": 2.},
        ]
        for module, fn in MODELS:
            cache = {}
            for change in changes:
                row = dict(self.base, velocity=5., **change)
                with self.subTest(model=fn.__name__, change=change):
                    self.assertEqual(fn(row, solver_cache=cache), fn(row))


if __name__ == "__main__":
    unittest.main()
