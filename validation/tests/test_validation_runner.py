"""The validator must expose errors and never manufacture a passing baseline."""

import csv
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

from validation.validate_curves import compare, run_validation, hvi_transition_velocity, overlay_ymax
from validation.validate_curves import Sheet, WorkbookError, normalize_inputs, read_baselines, read_workbook
from validation.validate_curves import pyblossum_reference_label
from validation.validate_curves import capture_baseline
from validation.validate_curves import automatic_baseline


def workbook_payload(*, last_cell='<v>0.5</v>'):
    """Minimal in-memory XML fixture; not a delivered or recalculated workbook."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('xl/workbook.xml', '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="reference" sheetId="8" r:id="rRef"/></sheets></workbook>''')
        archive.writestr('xl/_rels/workbook.xml.rels', '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rRef" Target="/xl/worksheets/independent.xml"/></Relationships>''')
        archive.writestr('xl/sharedStrings.xml', '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>proj_density</t></si><si><t>dc_BLE</t></si></sst>''')
        sheet = f'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>g/cm3</t></is></c><c r="C1"><v>2.8</v></c></row>
<row r="2"><c r="A2" t="inlineStr"><is><t>angle</t></is></c><c r="B2" t="inlineStr"><is><t>deg</t></is></c><c r="C2"><v>0</v></c></row>
<row r="4"><c r="B4" t="inlineStr"><is><t>velocity (km/s)</t></is></c><c r="C4" t="s"><v>1</v></c></row>
<row r="5"><c r="B5"><v>0.1</v></c><c r="C5"><f>1+0</f><v>1</v></c></row>
<row r="6"><c r="B6"><v>0.2</v></c><c r="C6">{last_cell}</c></row>
</sheetData></worksheet>'''
        archive.writestr('xl/worksheets/independent.xml', sheet)
    return buffer.getvalue()


def fixture_repository(root, blob=None):
    directory = root/'validation'
    directory.mkdir()
    (directory/'sample.xlsx').write_bytes(blob or workbook_payload())
    tolerance = {'rtol': 1e-6, 'atol_cm': 1e-9, 'reason': 'Synthetic test tolerance'}
    manifest = {'schema_version': 2, 'baseline_file': 'baselines.csv',
                'tolerances': {'regression': tolerance, 'reference': tolerance},
                'workbooks': {'sample.xlsx': {'model': 'mli', 'reference_header_row': 4,
                    'cases': {'C': {'inputs': {'proj_density': 2.8, 'angle': 0.},
                                    'units': {'proj_density': 'g/cm3', 'angle': 'deg'}, 'baseline_points': 2}}}}}
    (directory/'cases.json').write_text(json.dumps(manifest))
    (directory/'baselines.csv').write_text('case_id,velocity_km_s,diameter_cm\nsample_C,0.1,1\nsample_C,0.2,0.5\n')


class CommitBaselineTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_bootstrap_snapshot_tracks_manifest_and_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_repository(root)
            (root/'BLEs').mkdir()
            (root/'BLEs/BLE_MLI.py').write_text(
                "def mli_performance(row):\n    return row['proj_density'] / row['velocity']\n"
            )
            self.git(root, 'init')
            self.git(root, 'add', 'BLEs')
            self.git(root, '-c', 'user.email=test@example.invalid', '-c', 'user.name=Validation test',
                     'commit', '-m', 'model before manifest')
            manifest_path = root/'validation/cases.json'
            path, first, _ = automatic_baseline(root, manifest_path)
            self.assertTrue(first['bootstrap_configurations'])
            self.assertEqual(automatic_baseline(root, manifest_path)[0], path)

            manifest = json.loads(manifest_path.read_bytes())
            manifest['workbooks']['sample.xlsx']['cases']['C']['inputs']['proj_density'] = 4.
            manifest_path.write_text(json.dumps(manifest))
            changed_path, second, _ = automatic_baseline(root, manifest_path)
            self.assertNotEqual(changed_path, path)
            self.assertNotEqual(first['bootstrap_inputs']['manifest_sha256'],
                                second['bootstrap_inputs']['manifest_sha256'])
            _, diameters = read_baselines(changed_path).curve('sample_C', 2)
            np.testing.assert_array_equal(diameters, [40., 20.])

            (manifest_path.parent/'baselines.csv').write_text(
                'case_id,velocity_km_s,diameter_cm\nsample_C,0.2,1\nsample_C,0.4,0.5\n'
            )
            grid_path, third, _ = automatic_baseline(root, manifest_path)
            self.assertNotEqual(grid_path, changed_path)
            self.assertNotEqual(second['bootstrap_inputs']['baseline_sha256'],
                                third['bootstrap_inputs']['baseline_sha256'])
            velocities, diameters = read_baselines(grid_path).curve('sample_C', 2)
            np.testing.assert_array_equal(velocities, [.2, .4])
            np.testing.assert_array_equal(diameters, [20., 10.])

    def test_commits_advance_reference_and_repeated_runs_reuse_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_repository(root)
            (root/'BLEs').mkdir()
            model = root/'BLEs/BLE_MLI.py'
            model.write_text("def mli_performance(row):\n    return 1 / row['velocity']\n")
            self.git(root, 'init')
            self.git(root, 'config', 'user.email', 'test@example.invalid')
            self.git(root, 'config', 'user.name', 'Validation test')
            self.git(root, 'add', 'BLEs', 'validation')
            self.git(root, 'commit', '-m', 'first model')
            first = self.git(root, 'rev-parse', 'HEAD')
            manifest = root/'validation/cases.json'
            path, snapshot, dirty = automatic_baseline(root, manifest)
            self.assertFalse(dirty)
            self.assertEqual(snapshot['git_commit'], first)
            timestamp = path.stat().st_mtime_ns
            automatic_baseline(root, manifest)
            self.assertEqual(path.stat().st_mtime_ns, timestamp)
            model.write_text("def mli_performance(row):\n    return 2 / row['velocity']\n")
            self.git(root, 'add', 'BLEs')
            self.git(root, 'commit', '-m', 'second model')
            second = self.git(root, 'rev-parse', 'HEAD')
            path, snapshot, dirty = automatic_baseline(root, manifest)
            self.assertFalse(dirty)
            self.assertEqual(snapshot['git_commit'], first)
            self.assertEqual(path.stat().st_mtime_ns, timestamp)
            model.write_text("def mli_performance(row):\n    return 3 / row['velocity']\n")
            path, snapshot, dirty = automatic_baseline(root, manifest)
            self.assertTrue(dirty)
            self.assertEqual(snapshot['git_commit'], second)
            _, values = read_baselines(path).curve('sample_C', 2)
            # Cached second commit uses its code, never the uncommitted third version.
            np.testing.assert_array_equal(values, [20., 10.])
            model.write_text("def mli_performance(row):\n    raise ValueError('broken historical model')\n")
            self.git(root, 'add', 'BLEs')
            self.git(root, 'commit', '-m', 'broken model')
            broken = self.git(root, 'rev-parse', 'HEAD')
            with self.assertRaisesRegex(ValueError, 'broken historical model'):
                automatic_baseline(root, manifest)
            self.assertFalse((root/'validation/reports/baselines'/broken).exists())


class BaselineCaptureTests(unittest.TestCase):
    def test_capture_preserves_previous_files_and_records_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_repository(root)
            directory = root/'validation'
            before = {name: (directory/name).read_bytes() for name in ('cases.json', 'baselines.csv', 'sample.xlsx')}
            with patch('validation.validate_curves.calculate', return_value=np.array([2., 1.])):
                count, archive = capture_baseline(repo_root=root, label='checkpoint')
            self.assertEqual(count, 1)
            for name in ('cases.json', 'baselines.csv'):
                self.assertEqual((archive/name).read_bytes(), before[name])
            self.assertEqual((directory/'sample.xlsx').read_bytes(), before['sample.xlsx'])
            manifest = json.loads((directory/'cases.json').read_text())
            case = manifest['workbooks']['sample.xlsx']['cases']['C']
            self.assertEqual(case['baseline_origin']['inputs'], case['inputs'])
            self.assertEqual(case['baseline_origin']['version'], 'checkpoint')
            x, y = read_baselines(directory/'baselines.csv').curve('sample_C', 2)
            np.testing.assert_array_equal(y, [2., 1.])

    def test_failed_capture_leaves_files_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_repository(root)
            paths = [root/'validation'/name for name in ('cases.json', 'baselines.csv')]
            before = [p.read_bytes() for p in paths]
            with patch('validation.validate_curves.calculate', side_effect=ValueError('solver failed')):
                with self.assertRaisesRegex(ValueError, 'solver failed'):
                    capture_baseline(repo_root=root)
            self.assertEqual([p.read_bytes() for p in paths], before)
            self.assertFalse((root/'validation/reports').exists())


class OverlayScalingTests(unittest.TestCase):
    def test_reference_label_uses_stored_provenance(self):
        origin = {'git_commit': 'fe0a7df862041a9ea8816197b32eb9009beac35b'}
        self.assertEqual(pyblossum_reference_label({'baseline_origin': origin}),
                         'pyBLOSSUM reference (rev fe0a7df)')
        origin['date'] = '2024-08-26'
        self.assertEqual(pyblossum_reference_label({'baseline_origin': origin}),
                         'pyBLOSSUM reference (2024-08-26)')
        origin['version'] = 'v2.0'
        self.assertEqual(pyblossum_reference_label({'baseline_origin': origin}),
                         'pyBLOSSUM reference (v2.0)')
        self.assertEqual(pyblossum_reference_label({}), 'pyBLOSSUM reference')

    def test_transition_rules(self):
        for model, coefficient, exponent in [
                ('modified_jsc', 7, 1), ('reimerdes', 7, 1),
                ('mesh', 6.4, 1/3), ('stuffed', 6.5, .75), ('foam', 4, 1/3),
                ('hybrid', 6.5, 2/3), ('al_multishock', 6.4, .25),
                ('nextel', 6.4, .25), ('kevlar', 6.4, .25)]:
            with self.subTest(model=model):
                self.assertAlmostEqual(hvi_transition_velocity(model, {'angle': 60}),
                                       coefficient/np.cos(np.deg2rad(60))**exponent)
        for model, key in [('honeycomb', 'bumper_mat'), ('triple', 'outerBumper_mat')]:
            for material, coefficient in [('CFRP', 8.4), ('Other', 7), ('AA6061', 7)]:
                self.assertEqual(hvi_transition_velocity(model, {'angle': 0, key: material}), coefficient)
        for kind, coefficient in [('Baseline', 6), ('Toughened', 6.2), ('Enhanced', 6.4)]:
            self.assertEqual(hvi_transition_velocity('mli', {'angle': 0, 'type': kind}), coefficient)

    def test_angle_caps(self):
        for model, cap, extra in [('triple', 65, {'outerBumper_mat': 'CFRP'}),
                                  ('hybrid', 75, {})]:
            self.assertEqual(hvi_transition_velocity(model, dict(extra, angle=85)),
                             hvi_transition_velocity(model, dict(extra, angle=cap)))

    def test_exact_boundary_evaluation_and_automatic_scaling(self):
        inputs = {'angle': 30, 'type': 'Enhanced'}
        with patch('validation.validate_curves.calculate', return_value=np.array([.16])) as calculate:
            self.assertEqual(overlay_ymax('mli', inputs), .32)
            model, actual_inputs, velocities = calculate.call_args.args
            self.assertEqual(model, 'mli')
            self.assertEqual(actual_inputs, inputs)
            np.testing.assert_array_equal(velocities, [6.4/np.cos(np.deg2rad(30))**.25])
        for model in ('single', 'transparent'):
            self.assertIsNone(overlay_ymax(model, {}))


class WorkbookReaderTests(unittest.TestCase):
    def test_relationships_shared_inline_strings_and_cached_formula_values(self):
        tables = read_workbook(workbook_payload())
        self.assertEqual(set(tables), {'reference'})
        sheet = tables['reference']
        self.assertEqual(sheet.get('A1'), 'proj_density')
        self.assertEqual(sheet.get('B4'), 'velocity (km/s)')
        x, y = sheet.curve('B', 'C', 4)
        np.testing.assert_array_equal(x, [.1, .2])
        np.testing.assert_array_equal(y, [1., .5])

    def test_formula_without_cache_is_an_error_not_zero(self):
        sheet = read_workbook(workbook_payload(last_cell='<f>1/2</f>'))['reference']
        with self.assertRaisesRegex(WorkbookError, 'no cached value'):
            sheet.curve('B', 'C', 4)

    def test_missing_velocity_does_not_infer_or_extrapolate(self):
        sheet = Sheet('reference', {'B2': .1, 'C2': 1., 'C3': .5}, {})
        with self.assertRaisesRegex(WorkbookError, 'missing or nonnumeric'):
            sheet.curve('B', 'C', 1)

    def test_nonfinite_stored_inputs_are_errors(self):
        sheet = Sheet('pyBLOSSUM', {'C1': float('nan')}, {})
        with self.assertRaisesRegex(WorkbookError, 'nonfinite stored value'):
            sheet.get('C1')

    def test_units_are_explicit_and_original_inputs_are_preserved(self):
        original = {'wall_yield': 100., 'shield_C': 5000.}
        result = normalize_inputs(original, {'wall_yield': '(MPa)', 'shield_C': '(m/s)'})
        self.assertAlmostEqual(result['wall_yield'], 14.5038)
        self.assertEqual(result['shield_C'], 5.)
        self.assertEqual(original, {'wall_yield': 100., 'shield_C': 5000.})
        with self.assertRaisesRegex(WorkbookError, 'Unsupported wall_yield unit'):
            normalize_inputs({'wall_yield': 100.}, {'wall_yield': 'unknown'})


class ComparisonTests(unittest.TestCase):
    def test_absolute_plus_relative_limits_and_metrics(self):
        tolerance = {'rtol': .01, 'atol_cm': .001, 'reason': 'test'}
        result = compare([1.01, 2.], [1., 2.], tolerance)
        self.assertEqual(result['status'], 'PASS')
        result = compare([1.02, 2.], [1., 2.], tolerance)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['failed_points'], 1)
        self.assertAlmostEqual(result['max_relative_error_pct'], 2.)
        self.assertAlmostEqual(result['rms_error_cm'], np.sqrt(.02**2/2))

    def test_invalid_values_and_tolerances_never_pass(self):
        tolerance = {'rtol': 1e-6, 'atol_cm': 0., 'reason': 'test'}
        for actual, expected in [([], []), ([np.nan], [1.]), ([1.], [0.]), ([1.], [np.inf]), ([1.], [1., 2.])]:
            with self.subTest(actual=actual, expected=expected), self.assertRaises(ValueError):
                compare(actual, expected, tolerance)
        with self.assertRaises(ValueError):
            compare([1.], [1.], dict(tolerance, rtol=-1))


class ValidationDataTests(unittest.TestCase):
    def test_csv_coverage_matches_registered_json_configurations(self):
        directory = Path(__file__).resolve().parents[1]
        manifest = json.loads((directory/'cases.json').read_text())
        baselines = read_baselines(directory/manifest['baseline_file'])
        registered = {Path(filename).stem+'_'+column
                      for filename, spec in manifest['workbooks'].items()
                      for column in spec['cases']}
        self.assertEqual(set(baselines.points), registered)
        self.assertEqual(baselines.errors, {})
        for filename, spec in manifest['workbooks'].items():
            for column, config in spec['cases'].items():
                with self.subTest(workbook=filename, case=column):
                    velocity, diameter = baselines.curve(Path(filename).stem+'_'+column, config['baseline_points'])
                    self.assertEqual(len(velocity), len(diameter))
                    self.assertEqual(set(config['inputs']), set(config['units']))

    def test_reference_workbooks_have_no_python_or_blc_sheets(self):
        directory = Path(__file__).resolve().parents[1]
        manifest = json.loads((directory/'cases.json').read_text())
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        for filename in manifest['workbooks']:
            with self.subTest(workbook=filename), zipfile.ZipFile(directory/filename) as archive:
                sheets = ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns)
                names = {sheet.attrib['name'] for sheet in sheets}
                self.assertIn('reference', names)
                self.assertNotIn('pyBLOSSUM', names)
                self.assertNotIn('BLC', names)
                self.assertEqual({sheet.attrib['name'] for sheet in sheets if sheet.attrib.get('state', 'visible') == 'visible'}, {'reference'})


class RunnerTests(unittest.TestCase):
    def test_report_contains_separate_comparisons_data_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            before = (root/'validation/sample.xlsx').read_bytes()
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                report, output = run_validation(repo_root=root, plots=False)
            self.assertEqual(report['exit_code'], 0)
            self.assertEqual(report['counts'], {'PASS': 2, 'FAIL': 0, 'ERROR': 0})
            self.assertEqual(report['metadata']['workbook_source'], 'working-tree')
            self.assertEqual(report['metadata']['baseline_sha256'], read_baselines(root/'validation/baselines.csv').sha256)
            self.assertEqual(len(report['cases'][0]['workbook_sha256']), 64)
            self.assertEqual((root/'validation/sample.xlsx').read_bytes(), before)
            self.assertTrue((output/'index.html').exists())
            self.assertEqual(json.loads((output/'report.json').read_text())['exit_code'], 0)
            with (output/'summary.csv').open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 2)
            for name in ['sample_C_regression.csv', 'sample_C_reference.csv']:
                with (output/name).open() as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]['status'], 'PASS')

    def test_curve_drift_is_nonzero_and_does_not_update_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            before = (root/'validation/sample.xlsx').read_bytes()
            with patch('validation.validate_curves.calculate', return_value=np.array([1.1, .5])):
                report, output = run_validation(repo_root=root, plots=False)
            self.assertEqual(report['exit_code'], 1)
            self.assertEqual(report['counts']['FAIL'], 2)
            self.assertEqual((root/'validation/sample.xlsx').read_bytes(), before)

    def test_solver_failure_and_missing_cache_are_reported(self):
        for blob, message in [(workbook_payload(), 'deliberate solver failure'),
                              (workbook_payload(last_cell='<f>1/2</f>'), 'no cached value')]:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); fixture_repository(root, blob)
                with patch('validation.validate_curves.calculate', side_effect=ValueError('deliberate solver failure')):
                    report, output = run_validation(repo_root=root, plots=False)
                self.assertEqual(report['exit_code'], 1)
                self.assertEqual(report['counts']['ERROR'], 2)
                self.assertIn(message, json.dumps(report))

    def test_unregistered_workbook_and_csv_cases_are_not_skipped(self):
        for extra_file in [True, False]:
            with self.subTest(extra_file=extra_file), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); fixture_repository(root)
                if extra_file:
                    (root/'validation/new.xlsx').write_bytes(workbook_payload())
                else:
                    with (root/'validation/baselines.csv').open('a') as handle:
                        handle.write('extra_C,0.1,1\n')
                with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                    report, output = run_validation(repo_root=root, plots=False)
                self.assertEqual(report['exit_code'], 1)
                self.assertEqual(report['counts']['ERROR'], 1)
                if not extra_file:
                    extra = next(case for case in report['cases'] if case['id'] == 'extra_C')
                    self.assertEqual(extra['comparisons'][0]['comparison'], 'regression')

    def test_multiple_runs_have_separate_reports_and_selection_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                first, a = run_validation(repo_root=root, plots=False, comparison='regression')
                second, b = run_validation(repo_root=root, plots=False, comparison='reference')
            self.assertNotEqual(a, b)
            self.assertEqual(first['counts']['PASS'], 1)
            self.assertEqual(second['counts']['PASS'], 1)
            with self.assertRaisesRegex(ValueError, 'Unknown workbook'):
                run_validation(repo_root=root, selected=['missing.xlsx'], plots=False)

    def test_empty_manifest_never_passes_and_is_in_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            manifest = root/'validation/cases.json'
            spec = json.loads(manifest.read_text())
            spec['workbooks'] = {}
            manifest.write_text(json.dumps(spec))
            (root/'validation/sample.xlsx').unlink()
            (root/'validation/baselines.csv').write_text('case_id,velocity_km_s,diameter_cm\n')
            report, output = run_validation(repo_root=root, plots=False)
            self.assertEqual(report['exit_code'], 1)
            self.assertEqual(report['counts']['ERROR'], 1)
            with (output/'summary.csv').open() as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]['case'], 'coverage')

    def test_json_configuration_is_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            path = root/'validation/cases.json'
            manifest = json.loads(path.read_text())
            manifest['workbooks']['sample.xlsx']['cases']['C']['inputs']['proj_density'] = 3.
            path.write_text(json.dumps(manifest))
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])) as calculate:
                report, output = run_validation(repo_root=root, plots=False)
            self.assertEqual(report['exit_code'], 0)
            self.assertTrue(all(call.args[1]['proj_density'] == 3. for call in calculate.call_args_list))

    def test_regression_and_reference_sources_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root)
            workbook = root/'validation/sample.xlsx'; blob = workbook.read_bytes()
            workbook.unlink()
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])), patch('validation.validate_curves.workbook_bytes', side_effect=AssertionError('Excel must not be read')):
                report, output = run_validation(repo_root=root, comparison='regression', plots=False)
            self.assertEqual(report['counts'], {'PASS': 1, 'FAIL': 0, 'ERROR': 0})
            workbook.write_bytes(blob)
            (root/'validation/baselines.csv').unlink()
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                report, output = run_validation(repo_root=root, comparison='reference', plots=False)
            self.assertEqual(report['counts'], {'PASS': 1, 'FAIL': 0, 'ERROR': 0})

    def test_missing_or_duplicate_csv_points_are_errors(self):
        for content in ['case_id,velocity_km_s,diameter_cm\nsample_C,0.1,1\n',
                        'case_id,velocity_km_s,diameter_cm\nsample_C,0.1,1\nsample_C,0.1,1\n',
                        'case_id,velocity_km_s,diameter_cm\nsample_C,0.1,nan\nsample_C,0.2,.5\n']:
            with self.subTest(csv=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); fixture_repository(root)
                (root/'validation/baselines.csv').write_text(content)
                with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                    report, output = run_validation(repo_root=root, plots=False)
                self.assertEqual(report['counts'], {'PASS': 1, 'FAIL': 0, 'ERROR': 1})

    def test_reference_cache_error_does_not_block_csv_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); fixture_repository(root, workbook_payload(last_cell='<f>1/2</f>'))
            with patch('validation.validate_curves.calculate', return_value=np.array([1., .5])):
                report, output = run_validation(repo_root=root, plots=False)
            self.assertEqual(report['counts'], {'PASS': 1, 'FAIL': 0, 'ERROR': 1})


if __name__ == '__main__':
    unittest.main()
