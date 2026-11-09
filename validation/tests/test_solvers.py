"""Run with: python -B -m unittest discover -s validation/tests -v"""

import ast
import contextlib
import io
import itertools
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import warnings

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from BLEs import BLE_JSCwhipple as jsc
from BLEs import BLE_JSCwhipple_mod as modified
from BLEs import BLE_reimerdeswhipple as reimerdes
from BLEs import solver_utils as solvers

ROOT = Path(__file__).resolve().parents[2]
MODELS = {
    "JSCwhipple_performance": (jsc, jsc.JSCwhipple_performance),
    "modJSCwhipple_performance": (modified, modified.modJSCwhipple_performance),
    "reimerdes_performance": (reimerdes, reimerdes.reimerdes_performance),
}


class SolverValidationTests(unittest.TestCase):
    def test_hypervelocity_solve_on_each_side_of_switch(self):
        def derating(diameter):
            return 1. if diameter <= 1. else 2.**1.5

        for base, expected in [(.5, .5), (1., 1.), (4., 2.)]:
            with self.subTest(base=base):
                self.assertAlmostEqual(
                    solvers.solve_hypervelocity_diameter(base, 30., derating, context="test"),
                    expected,
                )
        with self.assertRaisesRegex(solvers.SolverError, "residual jumps across zero"):
            solvers.solve_hypervelocity_diameter(1.5, 30., derating, context="test")

    def solve(self, **kwargs):
        return solvers.checked_slsqp(
            lambda x: (x-2)**2, 1., lambda x: (x, 2.),
            context="test model diameter", **kwargs,
        )

    def test_real_solve(self):
        self.assertAlmostEqual(self.solve(), 2., places=6)

    def test_real_iteration_limit(self):
        with self.assertRaisesRegex(solvers.SolverError, "status=9.*Iteration limit"):
            self.solve(iterations=1)

    def test_failure_status_includes_context(self):
        with patch.object(solvers, "fmin_slsqp", return_value=(np.array([2.]), 0., 100, 9, "Iteration limit reached")):
            with self.assertRaisesRegex(solvers.SolverError, "test model diameter.*status=9"):
                self.solve()

    def test_invalid_results_and_objectives(self):
        for value in [np.nan, np.inf, -np.inf, 0., -1., 2+1j]:
            with self.subTest(value=value), patch.object(solvers, "fmin_slsqp", return_value=(np.array([value]), 0., 1, 0, "Success")):
                with self.assertRaises(solvers.SolverError):
                    self.solve()
        for objective in [np.nan, np.inf]:
            with self.subTest(objective=objective), patch.object(solvers, "fmin_slsqp", return_value=(np.array([2.]), objective, 1, 0, "Success")):
                with self.assertRaisesRegex(solvers.SolverError, "nonfinite objective"):
                    self.solve()

    def test_bounds_are_checked(self):
        with patch.object(solvers, "fmin_slsqp", return_value=(np.array([2.]), 0., 1, 0, "Success")):
            with self.assertRaisesRegex(solvers.SolverError, "outside bounds"):
                self.solve(bounds=[(0.1, 1.)])

    def test_success_with_large_residual_is_rejected(self):
        with patch.object(solvers, "fmin_slsqp", return_value=(np.array([1.]), 0., 1, 0, "Success")):
            with self.assertRaisesRegex(solvers.SolverError, "diameter residual.*exceeds tolerance"):
                self.solve()

    def test_piecewise_branch_only_skips_root_residual(self):
        with patch.object(solvers, "fmin_slsqp", return_value=(np.array([1.]), 0., 1, 0, "Success")):
            self.assertEqual(self.solve(residual_required=lambda x: False), 1.)
            with self.assertRaisesRegex(solvers.SolverError, "diameter residual"):
                self.solve(residual_required=lambda x: True)
        for value, status in [(np.nan, 0), (0., 0), (-1., 0), (1., 9)]:
            with self.subTest(value=value, status=status), patch.object(solvers, "fmin_slsqp", return_value=(np.array([value]), 0., 1, status, "test status")):
                with self.assertRaises(solvers.SolverError):
                    self.solve(residual_required=lambda x: False)
        with patch.object(solvers, "fmin_slsqp", return_value=(np.array([2.]), 0., 1, 0, "Success")):
            with self.assertRaisesRegex(solvers.SolverError, "outside bounds"):
                self.solve(bounds=[(.1, 1.)], residual_required=lambda x: False)

    def test_invalid_final_equation_is_rejected(self):
        for right in [np.nan, np.inf, -1., 0., 2+1j]:
            with self.subTest(right=right):
                with self.assertRaises(solvers.SolverError):
                    solvers.checked_slsqp(lambda x: (x-2)**2, 1., lambda x: (x, right), context="final equation")

    def test_trial_warnings_are_local(self):
        before = list(warnings.filters)
        def noisy(*args, **kwargs):
            warnings.warn("invalid trial point", RuntimeWarning)
            return np.array([2.]), 0., 1, 0, "Success"
        with patch.object(solvers, "fmin_slsqp", side_effect=noisy):
            self.assertEqual(self.solve(), 2.)
        self.assertEqual(warnings.filters, before)

    def test_derived_velocity_is_checked(self):
        for module in [jsc, modified]:
            with self.subTest(module=module.__name__), patch.object(module, "checked_slsqp", return_value=3.), patch.object(module.np, "isfinite", return_value=False):
                with self.assertRaisesRegex(solvers.SolverError, "derived transition velocity"):
                    module.vLV_solve_piek(.1, .2, 2.7, 73., 0.)


class ModelRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT/"validation/tests/fixtures/whipple_solver_baseline.json").read_text())

    def independently_checked_solve(self, objective, x0, diameters, **kwargs):
        result = solvers.checked_slsqp(objective, x0, diameters, **kwargs)
        if "residual_required" in kwargs and not kwargs["residual_required"](result):
            # This is an explicit piecewise limit, not an equality root.
            return result
        lower, upper = kwargs.get("bounds", [(1e-7, 100.)])[0]
        reference = brentq(lambda x: diameters(x)[0]-diameters(x)[1], lower, upper, xtol=1e-12)
        self.assertAlmostEqual(result, reference, delta=1e-6+1e-4*abs(reference))
        return result

    def test_baseline_and_independent_roots(self):
        accepted = 0
        # These four historical shatter points used the old transition solve.
        reimerdes_changed = {(45., 0., 5.), (45., .05, 5.),
                             (65., 0., 10.), (65., .05, 10.)}
        for name, angle, ad, standoff_mli, velocity, baseline in self.fixture["cases"]:
            row = dict(self.fixture["base_inputs"], angle=angle, AD_MLI=ad, S_MLI=standoff_mli, velocity=velocity)
            module, fn = MODELS[name]
            with self.subTest(model=name, angle=angle, AD_MLI=ad, S_MLI=standoff_mli, velocity=velocity):
                with patch.object(module, "checked_slsqp", side_effect=self.independently_checked_solve):
                    value = fn(row)
                    self.assertTrue(np.isfinite(value) and value > 0)
                    # Legacy SLSQP stopped early: measured changes are <0.07%.
                    if not (module is reimerdes and not standoff_mli
                            and (angle, ad, velocity) in reimerdes_changed):
                        self.assertAlmostEqual(value, baseline, delta=1e-6+1e-3*abs(baseline))
                    accepted += 1
        self.assertEqual(accepted, 135)

    def test_reimerdes_oblique_transition_uses_normal_velocity_once(self):
        row = dict(self.fixture["base_inputs"], angle=75., bumper_thick=.25,
                   wall_thick=1.5, proj_density=2.8, standoff=4.)
        # Independent root of the published low-speed and fragmentation equations.
        def low_diameter(normal_velocity):
            return ((1.5/1.8+.25)/(.796*.42*2.8**.518*normal_velocity**(2/3)))**(18/19)

        normal_transition = brentq(
            lambda v: v - (1.853+.397*(.25/low_diameter(v))**(-.565)), 2., 5.)
        angle = reimerdes.impact_angle_rad(row['angle'])
        cosine = np.cos(angle)
        low_transition = normal_transition/cosine
        high_transition = reimerdes.hvi_transition_velocity(row['angle'])
        velocities = np.array([.5, low_transition, low_transition+.2, high_transition])
        actual = reimerdes.reimerdes_curve(row, velocities)
        expected = [low_diameter(.5*cosine), low_diameter(normal_transition),
                    low_diameter(normal_transition)
                    + (actual[-1]-low_diameter(normal_transition))*.2/(high_transition-low_transition)]
        np.testing.assert_allclose(actual[:3], expected, rtol=1e-6)

    def test_reported_whipple_geometry_hits_the_diameter_gap(self):
        angle = np.deg2rad(60)
        hvi = 7 / np.cos(angle)
        for module, velocity in [(jsc, 15.), (reimerdes, hvi)]:
            with self.subTest(model=module.__name__):
                with self.assertRaisesRegex(solvers.SolverError, r"standoff/diameter = 30 switch \(0\.414 cm\)"):
                    module.dc_HV(.065, .28, 12.42, 40., 2.8, 2.7, angle, velocity, hvi)

    def test_capped_transition_matches_original_three_angles(self):
        for module in [jsc, modified]:
            for angle in [0., 45., 65.]:
                with self.subTest(model=module.__name__, angle=angle):
                    value = module.vLV_solve_piek(.1, .2, 2.7, 503*.145038, np.deg2rad(angle))
                    self.assertEqual(value, 2.6)
                    self.assertAlmostEqual(value/np.cos(np.deg2rad(angle)), 2.6/np.cos(np.deg2rad(angle)))

    def test_regime_boundary_continuity(self):
        for name, (module, fn) in MODELS.items():
            for angle in [0., 45., 65.]:
                for ad, s_mli in [(0., 0.), (.05, 0.), (.05, 1.)]:
                    row = dict(self.fixture["base_inputs"], angle=angle, AD_MLI=ad, S_MLI=s_mli)
                    radians = np.deg2rad(angle)
                    if s_mli:
                        v_lv = 2./np.cos(radians)
                    elif module in [jsc, modified]:
                        v_lv = 2.6/np.cos(radians)
                    else:
                        tb = row["bumper_thick"]+3*ad/2.78
                        v_lv = module.vLV_solve_reim(tb, row["wall_thick"], row["proj_density"])/np.cos(radians)
                    for boundary in [v_lv, 7./np.cos(radians)]:
                        with self.subTest(model=name, angle=angle, AD_MLI=ad, S_MLI=s_mli, boundary=boundary):
                            values = [fn(dict(row, velocity=boundary*(1+offset))) for offset in [-1e-7, 0., 1e-7]]
                            np.testing.assert_allclose(values, values[1], rtol=1e-5, atol=1e-6)

    def test_csv_whipple_regression_baselines(self):
        from validation.validate_curves import normalize_inputs, read_baselines
        manifest = json.loads((ROOT/'validation/cases.json').read_text())
        specification = manifest['workbooks']['whipple.xlsx']
        baselines = read_baselines(ROOT/'validation'/manifest['baseline_file'])
        array_functions = {"modJSCwhipple_performance": modified.modJSCwhipple_curve,
                           "reimerdes_performance": reimerdes.reimerdes_curve}
        for column, config in specification['cases'].items():
            model_name = {'modified_jsc': 'modJSCwhipple_performance',
                          'reimerdes': 'reimerdes_performance'}[specification['models_by_column'][column]]
            module, fn = MODELS[model_name]
            row = normalize_inputs(config['inputs'], config['units'])
            velocities, expected = baselines.curve('whipple_'+column, config['baseline_points'])
            with self.subTest(column=column, angle=row["angle"]):
                with patch.object(module, "checked_slsqp", side_effect=self.independently_checked_solve):
                    actual = [fn(dict(row, velocity=v)) for v in velocities]
                    array_values = array_functions[model_name](row, velocities)
                np.testing.assert_allclose(array_values, actual, rtol=1e-11, atol=1e-13)
                # The historical Reimerdes curve used a different angle rule.
                # The independent root check above covers the current model.
                if model_name == 'modJSCwhipple_performance':
                    np.testing.assert_allclose(actual, expected, rtol=1.5e-3, atol=1e-6)

    def test_cli_imports_and_outputs(self):
        source = (ROOT/"input_files/eval_example-whipple.csv").read_text().splitlines()
        headers = source[0].split(",")
        data = source[2].split(",")
        # Use the original no-MLI example, not a substitute internal-MLI case.
        for filename in ["BLE_JSCwhipple.py", "BLE_JSCwhipple_mod.py", "BLE_reimerdeswhipple.py", "BLE_NNOwhipple.py", "BLE_modNNOwhipple.py"]:
            with self.subTest(script=filename), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp)/"input.csv"
                config.write_text("\n".join([source[0], source[1], ",".join(data)])+"\n")
                output = io.StringIO()
                previous = Path.cwd()
                try:
                    os.chdir(tmp)
                    arguments = [filename, str(config)]
                    if filename == "BLE_JSCwhipple.py":
                        database = Path("data/database_whipple_pyBLOSSUM.csv")
                        database.parent.mkdir()
                        database.write_bytes((ROOT/database).read_bytes())
                        arguments.append("--data")
                    with patch.object(sys, "argv", arguments), patch.object(sys, "path", [str(ROOT/"BLEs"), *sys.path]), patch.object(pd.DataFrame, "apply", side_effect=AssertionError("row-wise CLI evaluation used")), contextlib.redirect_stdout(output):
                        runpy.run_path(str(ROOT/"BLEs"/filename), run_name="__main__")
                    self.assertNotIn("An error occurred", output.getvalue())
                    runs = list((Path(tmp)/"results").iterdir())
                    self.assertEqual(len(runs), 1)
                    run = runs[0]
                    self.assertRegex(run.name, r"^run_\d{8}_\d{6}_\d{6}$")
                    self.assertIn(str(run), output.getvalue())
                    self.assertEqual(len(list(run.iterdir())), 3 + ("--data" in arguments))
                    if "--data" in arguments:
                        self.assertEqual(len(list(run.glob("test_data_*.csv"))), 1)
                    config_path = next(run.glob("config_data_*.csv"))
                    self.assertEqual(pd.read_csv(config_path, nrows=1).loc[0, 'wall_yield'], 'MPa')
                    pd.testing.assert_frame_equal(pd.read_csv(config_path, skiprows=[1]), pd.read_csv(config, skiprows=[1]))
                    curve = pd.read_csv(next(run.glob("blc_data_*.csv")))
                    self.assertEqual(len(curve), 150)
                    self.assertTrue(np.isfinite(curve.to_numpy()).all())
                    scalar_models = {"BLE_JSCwhipple.py": jsc.JSCwhipple_performance,
                                     "BLE_JSCwhipple_mod.py": modified.modJSCwhipple_performance,
                                     "BLE_reimerdeswhipple.py": reimerdes.reimerdes_performance}
                    if filename in scalar_models:
                        row = pd.read_csv(config, skiprows=[1]).iloc[0].to_dict()
                        row['wall_yield'] *= .145038
                        cache = {}
                        expected = [scalar_models[filename](dict(row, velocity=float(v)), solver_cache=cache) for v in curve['velocity']]
                        np.testing.assert_allclose(curve.iloc[:, 1], expected, rtol=1e-11, atol=1e-13)
                finally:
                    os.chdir(previous)

    def test_cli_rejects_multiple_configurations_explicitly(self):
        lines = (ROOT/"input_files/eval_example-whipple.csv").read_text().splitlines()
        for filename in ["BLE_JSCwhipple.py", "BLE_JSCwhipple_mod.py", "BLE_reimerdeswhipple.py", "BLE_NNOwhipple.py", "BLE_modNNOwhipple.py"]:
            with self.subTest(script=filename), tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp)/"input.csv"
                config.write_text("\n".join([*lines, lines[2]])+"\n")
                previous = Path.cwd()
                output = io.StringIO()
                try:
                    os.chdir(tmp)
                    with patch.object(sys, "argv", [filename, str(config)]), patch.object(sys, "path", [str(ROOT/"BLEs"), *sys.path]), contextlib.redirect_stderr(output):
                        with self.assertRaises(SystemExit) as error:
                            runpy.run_path(str(ROOT/"BLEs"/filename), run_name="__main__")
                    self.assertEqual(error.exception.code, 1)
                    self.assertIn("Expected exactly one shield configuration", output.getvalue())
                    self.assertFalse((Path(tmp)/"results").exists())
                finally:
                    os.chdir(previous)

    def test_cli_exit_status_and_diagnostics(self):
        source = (ROOT/"input_files/eval_example-whipple.csv").read_text().splitlines()
        command = [sys.executable, '-B', str(ROOT/'BLEs/BLE_JSCwhipple.py')]
        with tempfile.TemporaryDirectory() as tmp:
            valid = Path(tmp)/'valid.csv'
            valid.write_text('\n'.join(source)+'\n')
            malformed = Path(tmp)/'malformed.csv'
            malformed.write_text('wrong_column\nunits\n1\n')
            gap = Path(tmp)/'gap.csv'
            data = dict(zip(source[0].split(','), source[2].split(',')))
            data.update(angle=60, bumper_thick=.065, wall_thick=.28, standoff=12.42,
                        wall_yield=40/.145038, proj_density=2.8, bumper_density=2.7)
            gap.write_text('\n'.join([*source[:2], ','.join(map(str, data.values()))])+'\n')
            for path, status, diagnostic in [
                (valid, 0, ''),
                (Path(tmp)/'missing.csv', 1, 'missing.csv'),
                (malformed, 1, 'wall_yield'),
                (gap, 1, 'residual jumps across zero'),
            ]:
                with self.subTest(file=path.name):
                    result = subprocess.run([*command, str(path)], cwd=tmp, capture_output=True, text=True)
                    self.assertEqual(result.returncode, status, result.stderr)
                    if diagnostic:
                        self.assertIn(diagnostic, result.stderr)


class GuiFailureTests(unittest.TestCase):
    def test_solver_errors_are_displayed_without_showing_or_saving_curve(self):
        # Exercise the real handler without starting Qt or background threads.
        tree = ast.parse((ROOT/"src/GUI_whipple.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MyApp")
        handler = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "on_run_button_clicked")
        message_box, plot_window = Mock(), Mock()
        namespace = {"pd": pd, "QMessageBox": message_box, "PlotWindow": plot_window}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "GUI_whipple_handler", "exec"), namespace)
        fields = ["angle", "density0", "thickness1", "density1", "standoff", "thickness2", "density2", "yield2", "MLIad", "MLIs"]
        for label, key in [("JSC Whipple", "JSCwhipple_curve"), ("JSC Whipple (mod)", "modJSCwhipple_curve"), ("Reimerdes-modified NNO", "reimerdes_curve"), ("New non-optimum (NNO)", "NNO_curve"), ("Christiansen-modified NNO", "modNNO_curve")]:
            with self.subTest(model=label):
                message_box.reset_mock(); plot_window.reset_mock()
                widget = Mock()
                widget.mli_type_dropdown.currentText.return_value = "None"
                for field in fields:
                    getattr(widget, field+"_entry").text.return_value = "1"
                item = Mock(); item.text.return_value = label
                widget.list_widget.selectedItems.return_value = [item]
                widget.packages = {"itertools": itertools, "color_line_style_pairs": [("black", "-")], "np": np, "pd": pd, key: Mock(side_effect=solvers.SolverError("test model: solver failed"))}
                with contextlib.redirect_stdout(io.StringIO()):
                    namespace["on_run_button_clicked"](widget)
                message_box.critical.assert_called_once_with(widget, "Error", "test model: solver failed")
                plot_window.return_value.show.assert_not_called()
                plot_window.return_value.canvas.draw.assert_not_called()
                plot_window.return_value.figure.savefig.assert_not_called()


if __name__ == "__main__":
    unittest.main()
