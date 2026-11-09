"""Compare NumPy curves against the retained scalar model implementations."""

import ast
import contextlib
from datetime import datetime
import io
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd
import pyBLOSSUM

from BLEs import BLE_JSCwhipple as jsc
from BLEs import BLE_JSCwhipple_mod as modified
from BLEs import BLE_reimerdeswhipple as reimerdes
from BLEs import BLE_NNOwhipple as nno
from BLEs import BLE_modNNOwhipple as mod_nno
from BLEs import results_utils
from BLEs.solver_utils import SolverError

ROOT = Path(__file__).resolve().parents[2]
MODELS = [
    (jsc, jsc.JSCwhipple_performance, jsc.JSCwhipple_curve),
    (modified, modified.modJSCwhipple_performance, modified.modJSCwhipple_curve),
    (reimerdes, reimerdes.reimerdes_performance, reimerdes.reimerdes_curve),
    (nno, nno.NNO_performance, nno.NNO_curve),
    (mod_nno, mod_nno.modNNO_performance, mod_nno.modNNO_curve),
]


class ArrayCurveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads((ROOT/"validation/tests/fixtures/whipple_solver_baseline.json").read_text())["base_inputs"]

    def scalar_curve(self, module, scalar, config, velocities):
        cache = {}
        return np.array([
            scalar(dict(config, velocity=float(v)), **({"solver_cache": cache} if module in [jsc, modified, reimerdes] else {}))
            for v in velocities
        ])

    def boundaries(self, module, config):
        radians = module.impact_angle_rad(config['angle'])
        cosine = np.cos(radians)
        if config['S_MLI'] > 0:
            low = 2/cosine**1.5 if module is mod_nno else 2/cosine
        elif module is nno:
            low = 3/cosine
        elif module is mod_nno:
            low = 3/cosine**1.5
        else:
            tb = config['bumper_thick']+3*config['AD_MLI']/2.78
            if module is reimerdes:
                low = module.vLV_solve_reim(tb, config['wall_thick'], config['proj_density'])/cosine
            else:
                low = module.vLV_solve_piek(tb, config['wall_thick'], config['proj_density'], config['wall_yield'], radians)/cosine
        return low, 7/cosine

    def test_dense_curves_match_scalar_for_all_five_models(self):
        velocities = np.linspace(.1, 15., 150)
        for module, scalar, curve in MODELS:
            for angle, ad, s_mli in [(0., 0., 0.), (45., .05, 0.), (75., .05, 1.)]:
                config = dict(self.base, angle=angle, AD_MLI=ad, S_MLI=s_mli)
                with self.subTest(model=curve.__name__, angle=angle, AD_MLI=ad, S_MLI=s_mli):
                    expected = self.scalar_curve(module, scalar, config, velocities)
                    actual = curve(config, velocities)
                    self.assertEqual(actual.dtype, np.dtype(float))
                    np.testing.assert_allclose(actual, expected, rtol=1e-11, atol=1e-13)

    def test_exact_boundaries_neighbors_order_and_duplicates(self):
        for module, scalar, curve in MODELS:
            for angle in [0., 45., 65., 75.]:
                for ad, s_mli in [(0., 0.), (.05, 0.), (.05, 1.)]:
                    config = dict(self.base, angle=angle, AD_MLI=ad, S_MLI=s_mli)
                    low, high = self.boundaries(module, config)
                    velocities = np.array([high*1.2, np.nextafter(low, 0.), low, np.nextafter(low, np.inf), (low+high)/2, np.nextafter(high, 0.), high, np.nextafter(high, np.inf), .1, high, low])
                    with self.subTest(model=curve.__name__, angle=angle, AD_MLI=ad, S_MLI=s_mli):
                        expected = self.scalar_curve(module, scalar, config, velocities)
                        np.testing.assert_allclose(curve(config, velocities), expected, rtol=1e-11, atol=1e-13)

    def test_empty_and_invalid_velocity_arrays(self):
        for module, scalar, curve in MODELS:
            with self.subTest(model=curve.__name__):
                empty = curve({}, [])
                self.assertEqual(empty.shape, (0,))
                self.assertEqual(empty.dtype, np.dtype(float))
                for invalid in [0., [[1., 2.]], [0.], [-1.], [np.nan], [np.inf]]:
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        curve(self.base, invalid)

    def test_input_arrays_and_configurations_are_unchanged(self):
        for module, scalar, curve in MODELS:
            config = dict(self.base, AD_MLI=.05, S_MLI=1.)
            previous = dict(config)
            velocities = np.array([1., 3., 5.])
            velocities.setflags(write=False)
            with self.subTest(model=curve.__name__):
                curve(config, velocities)
                self.assertEqual(config, previous)
                np.testing.assert_array_equal(velocities, [1., 3., 5.])

    def test_solver_counts_match_cached_scalar_path(self):
        velocities = np.linspace(.1, 15., 150)
        for module, scalar, curve in MODELS[:3]:
            for angle in [0., 45., 65.]:
                config = dict(self.base, angle=angle, AD_MLI=0., S_MLI=0.)
                with self.subTest(model=curve.__name__, angle=angle):
                    with patch.object(module, 'dc_HV', wraps=module.dc_HV) as solve:
                        self.scalar_curve(module, scalar, config, velocities)
                        scalar_count = solve.call_count
                    with patch.object(module, 'dc_HV', wraps=module.dc_HV) as solve:
                        curve(config, velocities)
                        self.assertEqual(solve.call_count, scalar_count)

    def test_inactive_high_speed_branch_does_not_solve(self):
        for module, scalar, curve in MODELS[:3]:
            with self.subTest(model=curve.__name__), patch.object(module, 'dc_HV', side_effect=AssertionError('unexpected high-speed solve')):
                result = curve(self.base, [.1, .5])
                self.assertTrue(np.isfinite(result).all())

    def test_scalar_solver_failures_propagate(self):
        for module, scalar, curve in MODELS[:3]:
            with self.subTest(model=curve.__name__), patch.object(module, 'dc_HV', side_effect=SolverError('failed high-speed solve')):
                with self.assertRaisesRegex(SolverError, 'failed high-speed solve'):
                    curve(self.base, [20.])

    def test_modified_nno_both_kh_branches(self):
        velocities = np.array([.1, 3., 5., 7., 15.])
        for thickness in [.01, .2]:
            config = dict(self.base, bumper_thick=thickness)
            with self.subTest(bumper_thick=thickness):
                expected = self.scalar_curve(mod_nno, mod_nno.modNNO_performance, config, velocities)
                np.testing.assert_allclose(mod_nno.modNNO_curve(config, velocities), expected, rtol=1e-11, atol=1e-13)


class GuiArrayIntegrationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT/'src/GUI_whipple.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MyApp')
        handler = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'on_run_button_clicked')
        self.message_box, self.plot_window = Mock(), Mock()
        self.namespace = {
            'pd': pd, 'os': os, 'QMessageBox': self.message_box, 'PlotWindow': self.plot_window,
            'create_run_directory': results_utils.create_run_directory,
            'write_config_csv': results_utils.write_config_csv,
        }
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'GUI_whipple_handler', 'exec'), self.namespace)
        self.widget = Mock()
        widget = self.widget
        widget.mli_type_dropdown.currentText.return_value = 'None'
        values = {'angle': '0', 'density0': '2.7', 'thickness1': '.1', 'density1': '2.77', 'standoff': '10', 'thickness2': '.2', 'density2': '2.8', 'yield2': '503', 'MLIad': '.05', 'MLIs': '1'}
        for field, value in values.items():
            getattr(widget, field+'_entry').text.return_value = value
        for i in range(3):
            getattr(widget, f'material{i}_dropdown').currentText.return_value = 'Aluminium'
        for field in ['plot_test_data', 'save_plot', 'save_data']:
            getattr(widget, field+'_checkbox').isChecked.return_value = False
        labels = ['New non-optimum (NNO)', 'Christiansen-modified NNO', 'Reimerdes-modified NNO', 'JSC Whipple', 'JSC Whipple (mod)']
        items = []
        for label in labels:
            item = Mock(); item.text.return_value = label
            items.append(item)
        widget.list_widget.selectedItems.return_value = items
        self.curves = {fn.__name__: Mock(wraps=fn) for module, scalar, fn in MODELS}
        widget.packages = {'itertools': itertools, 'color_line_style_pairs': [('black', '-')]*5, 'np': np, 'pd': pd, **self.curves}

    def run_handler(self):
        self.namespace['on_run_button_clicked'](self.widget)

    def test_all_five_selected_curves_use_arrays_without_dataframe_apply(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(pd.DataFrame, 'apply', side_effect=AssertionError('row-wise evaluation used')), contextlib.redirect_stdout(io.StringIO()):
            self.namespace['root_dir'] = tmp
            self.run_handler()
            self.assertFalse((Path(tmp)/'results').exists())
        self.message_box.critical.assert_not_called()
        for fn in self.curves.values():
            fn.assert_called_once()
            self.assertIsInstance(fn.call_args.args[0], dict)
            self.assertEqual(fn.call_args.args[1].shape, (150,))
        self.assertEqual(self.plot_window.return_value.figure.add_subplot.return_value.plot.call_count, 5)
        self.plot_window.return_value.canvas.draw.assert_called_once()
        self.plot_window.return_value.show.assert_called_once()

    def test_mli_mode_controls_solver_and_saved_configuration(self):
        widget = self.widget
        widget.list_widget.selectedItems.return_value = widget.list_widget.selectedItems()[0:1]
        widget.save_data_checkbox.isChecked.return_value = True
        widget.save_plot_checkbox.isChecked.return_value = True
        for mode, expected in [('Internal', (.05, 1.)), ('External', (.05, 0.)), ('None', (0., 0.))]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                self.namespace['root_dir'] = tmp
                widget.mli_type_dropdown.currentText.return_value = mode
                self.run_handler()
                inputs = self.curves['NNO_curve'].call_args.args[0]
                self.assertEqual((inputs['AD_MLI'], inputs['S_MLI']), expected)
                run, = (Path(tmp)/'results').iterdir()
                self.assertTrue(run.name.startswith('run_'))
                self.assertEqual(self.plot_window.return_value.figure.savefig.call_args.args[0].parent, run)
                self.assertEqual(len(list(run.glob('blc_data_*.csv'))), 1)
                path, = run.glob('config_data_*.csv')
                units = pd.read_csv(path, nrows=1).iloc[0]
                self.assertEqual((units['AD_MLI'], units['S_MLI'], units['wall_yield']), ('g/cm2', 'cm', 'MPa'))
                config = pd.read_csv(path, skiprows=[1]).iloc[0]
                self.assertEqual((config['AD_MLI'], config['S_MLI']), expected)
                self.assertAlmostEqual(config['wall_yield'], 503)
        self.message_box.critical.assert_not_called()

    def test_invalid_inputs_and_diameters_stop_before_plotting(self):
        widget = self.widget
        for field, value in [('angle', 'nan'), ('standoff', 'inf'), ('density0', '0')]:
            with self.subTest(field=field, value=value):
                entry = getattr(widget, field+'_entry')
                previous = entry.text.return_value
                entry.text.return_value = value
                self.run_handler()
                self.message_box.critical.assert_called_once()
                self.message_box.reset_mock()
                entry.text.return_value = previous
        for curve in self.curves.values():
            curve.assert_not_called()

        widget.mli_type_dropdown.currentText.return_value = 'Internal'
        widget.MLIs_entry.text.return_value = ''
        self.run_handler()
        self.message_box.critical.assert_called_once()
        self.message_box.reset_mock()

        widget.mli_type_dropdown.currentText.return_value = 'None'
        self.curves['NNO_curve'].return_value = np.full(150, np.nan)
        self.run_handler()
        self.message_box.critical.assert_called_once_with(
            widget, 'Error', 'New non-optimum (NNO) returned an invalid diameter curve.',
        )
        self.plot_window.assert_not_called()


class ResultsDirectoryTests(unittest.TestCase):
    def test_identical_timestamps_get_distinct_run_directories(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(results_utils, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 11, 9, 12, 34, 56, 123456)
            first, stamp = results_utils.create_run_directory(tmp)
            second, _ = results_utils.create_run_directory(tmp)
            self.assertEqual(stamp, '20261109_123456')
            self.assertEqual(first.name, 'run_20261109_123456_123456')
            self.assertEqual(second.name, first.name+'_1')
            self.assertTrue(first.is_dir() and second.is_dir())


class LauncherTests(unittest.TestCase):
    def test_opens_and_tracks_an_analysis_window(self):
        widget = Mock()
        widget.configuration_dropdown.currentText.return_value = 'Whipple shield'
        widget.configuration_to_module = {'Whipple shield': 'src.GUI_whipple'}
        widget.analysis_windows = set()
        with patch.object(pyBLOSSUM, 'import_module') as load:
            pyBLOSSUM.MyApp.on_analyse_button_clicked(widget)
            load.assert_called_once_with('src.GUI_whipple')
            window = load.return_value.MyApp.return_value
            window.show.assert_called_once()
            self.assertIn(window, widget.analysis_windows)
            window.destroyed.connect.call_args.args[0]()
            self.assertEqual(widget.analysis_windows, set())

    def test_reports_an_analysis_import_error(self):
        widget = Mock()
        widget.configuration_dropdown.currentText.return_value = 'Whipple shield'
        widget.configuration_to_module = {'Whipple shield': 'src.GUI_whipple'}
        with patch.object(pyBLOSSUM, 'import_module', side_effect=ImportError('test failure')), patch.object(pyBLOSSUM, 'QMessageBox') as messages:
            pyBLOSSUM.MyApp.on_analyse_button_clicked(widget)
        messages.critical.assert_called_once_with(
            widget, 'Launch error', 'Could not open the analysis window.\ntest failure',
        )


if __name__ == '__main__':
    unittest.main()
