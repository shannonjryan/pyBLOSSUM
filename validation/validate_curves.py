"""Compare JSON configurations with CSV baselines and XLSX reference curves.

Run from the repository root: python validation/validate_curves.py
Use --git-ref HEAD to explicitly read committed workbook snapshots instead.
"""

import argparse
from dataclasses import dataclass
import io
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import html
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

os.environ['MPLBACKEND'] = 'Agg'
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import scipy

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


class WorkbookError(ValueError):
    """A validation workbook is missing required or usable stored data."""


@dataclass
class Sheet:
    name: str
    cells: dict
    errors: dict

    def get(self, address, default=None):
        if address in self.errors:
            raise WorkbookError(f"{self.name}!{address}: {self.errors[address]}")
        value = self.cells.get(address, default)
        if isinstance(value, (float, int)) and not np.isfinite(value):
            raise WorkbookError(f'{self.name}!{address}: nonfinite stored value')
        return value

    def curve(self, x_column, y_column, header_row):
        rows = [int(re.search(r'\d+$', address).group()) for address in self.cells
                if re.fullmatch(y_column+r'\d+', address) and int(re.search(r'\d+$', address).group()) > header_row]
        rows += [int(re.search(r'\d+$', address).group()) for address in self.errors
                 if re.fullmatch(y_column+r'\d+', address) and int(re.search(r'\d+$', address).group()) > header_row]
        if not rows:
            raise WorkbookError(f'{self.name}!{y_column}: no stored curve points')
        pairs = []
        for row in range(header_row+1, max(rows)+1):
            x, y = self.get(f'{x_column}{row}'), self.get(f'{y_column}{row}')
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise WorkbookError(f'{self.name}!{x_column}{row}/{y_column}{row}: missing or nonnumeric curve point')
            pairs.append((x, y))
        values = np.asarray(pairs, dtype=float)
        if len(values) < 2 or not np.isfinite(values).all() or np.any(values <= 0):
            raise WorkbookError(f'{self.name}!{y_column}: curve needs at least two finite, positive points')
        return values[:, 0], values[:, 1]


def read_workbook(blob):
    """Resolve sheet relationships and read shared/inline strings and caches."""
    tables = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(t.text or '' for t in si.findall('.//s:t', NS))
                      for si in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        relations = {r.attrib['Id']: r.attrib['Target']
                     for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
            name = sheet.attrib['name']
            if name.casefold() != 'reference':
                continue
            target = relations[sheet.attrib[REL_ID]]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            cells, errors = {}, {}
            for cell in ET.fromstring(archive.read(target)).findall('.//s:c', NS):
                address = cell.attrib['r']
                value, formula = cell.find('s:v', NS), cell.find('s:f', NS)
                inline = cell.find('s:is', NS)
                kind = cell.attrib.get('t')
                if kind == 'e':
                    errors[address] = f'Excel error {value.text if value is not None else "unknown"}'
                elif value is not None and value.text is not None:
                    if kind == 's':
                        cells[address] = shared[int(value.text)]
                    elif kind in ('str', 'b'):
                        cells[address] = value.text
                    else:
                        cells[address] = float(value.text)
                elif inline is not None:
                    cells[address] = ''.join(t.text or '' for t in inline.findall('.//s:t', NS))
                elif formula is not None:
                    errors[address] = 'formula has no cached value; recalculate and save in Excel first'
            tables[name.casefold()] = Sheet(name, cells, errors)
    if 'reference' not in tables:
        raise WorkbookError('Missing reference sheet')
    return tables


@dataclass
class Baselines:
    points: dict
    errors: dict
    source_rows: dict
    sha256: str

    def curve(self, case_id, expected_count):
        if case_id in self.errors:
            raise ValueError('; '.join(self.errors[case_id]))
        if case_id not in self.points:
            raise ValueError(f'Missing CSV baseline for {case_id}')
        values = np.asarray(self.points[case_id], dtype=float)
        if len(values) != expected_count:
            raise ValueError(f'{case_id}: expected {expected_count} baseline points, found {len(values)}')
        return values[:, 0], values[:, 1]


def read_baselines(path):
    """Read full-precision CSV data; malformed cases never become empty passes."""
    content = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != ['case_id', 'velocity_km_s', 'diameter_cm']:
        raise ValueError('Baseline CSV needs columns: case_id,velocity_km_s,diameter_cm')
    points, errors, source_rows, seen = {}, {}, {}, set()
    for row_number, row in enumerate(reader, 2):
        case_id = (row.get('case_id') or '').strip()
        if not case_id:
            errors.setdefault(f'row_{row_number}', []).append(f'CSV row {row_number}: missing case_id')
            continue
        source_rows.setdefault(case_id, []).append(row_number)
        try:
            if None in row:
                raise ValueError('unexpected extra fields')
            velocity, diameter = float(row['velocity_km_s']), float(row['diameter_cm'])
            if not np.isfinite([velocity, diameter]).all() or min(velocity, diameter) <= 0:
                raise ValueError('velocity and diameter must be finite and positive')
            if (case_id, velocity) in seen:
                raise ValueError(f'duplicate velocity {velocity:g}')
            seen.add((case_id, velocity))
            points.setdefault(case_id, []).append((velocity, diameter))
        except (TypeError, ValueError, KeyError) as exc:
            errors.setdefault(case_id, []).append(f'CSV row {row_number}: {exc}')
    return Baselines(points, errors, source_rows, hashlib.sha256(content).hexdigest())


def normalize_inputs(inputs, units):
    result = dict(inputs)
    if 'wall_yield' in result:
        unit = str(units.get('wall_yield', '')).strip('() ').lower()
        if unit == 'mpa':
            result['wall_yield'] *= .145038
        elif unit != 'ksi':
            raise WorkbookError(f'Unsupported wall_yield unit: {unit!r}')
    if 'shield_C' in result:
        unit = str(units.get('shield_C', '')).strip('() ').lower()
        if unit == 'm/s':
            result['shield_C'] /= 1000.
        elif unit != 'km/s':
            raise WorkbookError(f'Unsupported shield_C unit: {unit!r}')
    return result


def git_commit(repo_root, ref):
    result = subprocess.run(['git', '-C', str(repo_root), 'rev-parse', '--verify', '--end-of-options', ref+'^{commit}'], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def workbook_bytes(path, repo_root, commit=None):
    path, repo_root = Path(path), Path(repo_root)
    if commit is None:
        try:
            return path.read_bytes()
        except PermissionError as exc:
            raise WorkbookError(f'Cannot read {path.name}. Make it available locally/close exclusive locks, or explicitly use --git-ref HEAD for committed workbooks.') from exc
    relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    try:
        return subprocess.run(['git', '-C', str(repo_root), 'show', f'{commit}:{relative}'], capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        raise WorkbookError(f'{path.name}: cannot read committed workbook at {commit[:12]}: {exc.stderr.decode(errors="replace").strip()}') from exc

MODELS = {
    'modified_jsc': ('BLE_JSCwhipple_mod', 'modJSCwhipple_curve', True),
    'reimerdes': ('BLE_reimerdeswhipple', 'reimerdes_curve', True),
    'single': ('BLE_singleWall', 'singleWall_performance', False),
    'transparent': ('BLE_transparent', 'transparent_performance', False),
    'mesh': ('BLE_meshDB', 'meshDB_performance', False),
    'stuffed': ('BLE_stuffedWhipple', 'stuffedWhipple_performance', False),
    'mli': ('BLE_MLI', 'mli_performance', False),
    'honeycomb': ('BLE_SRL', 'SRL_double_performance', False),
    'foam': ('BLE_foamSP', 'foamSP_performance', False),
    'triple': ('BLE_SRL', 'SRL_triple_performance', False),
    'hybrid': ('BLE_multishock', 'multishockHybrid_performance', False),
    'al_multishock': ('BLE_multishock', 'multishockAl_performance', False),
    'nextel': ('BLE_multishock', 'multishockNextel_performance', False),
    'kevlar': ('BLE_multishock', 'multishockKevlar_performance', False),
}


def resolve_model(model, inputs):
    if model == 'sandwich':
        return {'Honeycomb': 'honeycomb', 'Foam': 'foam'}[inputs['type']]
    if model == 'multishock':
        return {'Hybrid shield': 'hybrid', 'Aluminium rear wall': 'al_multishock',
                'Nextel rear wall': 'nextel', 'Kevlar rear wall': 'kevlar'}[inputs['type']]
    if model not in MODELS:
        raise ValueError(f'Unregistered model: {model}')
    return model


@lru_cache(maxsize=None)
def model_function(model):
    module, function, array = MODELS[model]
    imported = importlib.import_module('BLEs.'+module)
    # Commits before the array API remain valid comparison sources.
    if array and not hasattr(imported, function):
        function = {'modified_jsc': 'modJSCwhipple_performance',
                    'reimerdes': 'reimerdes_performance'}[model]
        array = False
    return getattr(imported, function), array


def calculate(model, inputs, velocities):
    function, array = model_function(model)
    if array:
        result = np.asarray(function(inputs, velocities), dtype=float)
    else:
        result = np.fromiter((function(dict(inputs, velocity=float(v))) for v in velocities), dtype=float, count=len(velocities))
    if result.shape != velocities.shape or not np.isfinite(result).all() or np.any(result <= 0):
        raise ValueError('Model returned missing, nonfinite, nonpositive, or incorrectly shaped diameters')
    return result


def check_tolerance(tolerance):
    rtol, atol = tolerance['rtol'], tolerance['atol_cm']
    if not np.isfinite([rtol, atol]).all() or min(rtol, atol) < 0:
        raise ValueError('Tolerances must be finite and nonnegative')
    if not tolerance.get('reason'):
        raise ValueError('Each tolerance needs a documented reason')


def compare(actual, expected, tolerance):
    check_tolerance(tolerance)
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if actual.ndim != 1 or not actual.size or actual.shape != expected.shape:
        raise ValueError('Comparison needs equally sized, nonempty 1-D curves')
    if not np.isfinite(actual).all() or not np.isfinite(expected).all() or np.any(actual <= 0) or np.any(expected <= 0):
        raise ValueError('Comparison curves must contain finite, positive diameters')
    error = actual-expected
    relative = error/expected
    failed = np.abs(error) > tolerance['atol_cm']+tolerance['rtol']*np.abs(expected)
    return {'status': 'FAIL' if np.any(failed) else 'PASS', 'points': int(actual.size),
            'failed_points': int(np.count_nonzero(failed)),
            'max_abs_error_cm': float(np.max(np.abs(error))),
            'rms_error_cm': float(np.sqrt(np.mean(error**2))),
            'max_relative_error_pct': float(100*np.max(np.abs(relative))),
            'rms_relative_error_pct': float(100*np.sqrt(np.mean(relative**2)))}


def write_points(path, velocities, expected, actual, tolerance):
    fields = ['velocity_km_s', 'stored_diameter_cm', 'current_diameter_cm',
              'signed_error_cm', 'relative_error_pct', 'allowed_error_cm', 'status']
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, (v, stored) in enumerate(zip(velocities, expected)):
            allowed = tolerance['atol_cm']+tolerance['rtol']*abs(stored)
            row = {'velocity_km_s': float(v), 'stored_diameter_cm': float(stored), 'allowed_error_cm': float(allowed), 'status': 'ERROR'}
            if actual is not None:
                error = actual[i]-stored
                row.update(current_diameter_cm=float(actual[i]), signed_error_cm=float(error),
                           relative_error_pct=float(100*error/stored),
                           status='PASS' if abs(error) <= allowed else 'FAIL')
            writer.writerow(row)


def hvi_transition_velocity(model, inputs):
    """HVI boundary in km/s, matching the model's material and angle rules."""
    if model in ('single', 'transparent'):
        return None
    angle = inputs['angle']
    if model in ('modified_jsc', 'reimerdes'):
        module = importlib.import_module('BLEs.'+MODELS[model][0])
        return float(module.hvi_transition_velocity(angle))
    if model == 'triple':
        angle = min(angle, 65)
    elif model == 'hybrid':
        angle = min(angle, 75)
    cosine = np.cos(np.deg2rad(angle))
    if model in ('honeycomb', 'triple'):
        material = inputs['bumper_mat' if model == 'honeycomb' else 'outerBumper_mat']
        coefficient, exponent = (8.4 if material == 'CFRP' else 7), 1
    elif model == 'mli':
        coefficient, exponent = {'Baseline': (6, .5), 'Toughened': (6.2, .25),
                                 'Enhanced': (6.4, .25)}[inputs['type']]
    else:
        coefficient, exponent = {'mesh': (6.4, 1/3), 'stuffed': (6.5, .75),
                                 'foam': (4, 1/3), 'hybrid': (6.5, 2/3),
                                 'al_multishock': (6.4, .25), 'nextel': (6.4, .25),
                                 'kevlar': (6.4, .25)}[model]
    return float(coefficient/cosine**exponent)


def overlay_ymax(model, inputs):
    """Evaluate the current equation at the exact HVI boundary, off-grid if needed."""
    velocity = hvi_transition_velocity(model, inputs)
    if velocity is None:
        return None
    return 2*float(calculate(model, inputs, np.array([velocity]))[0])


def pyblossum_reference_label(case):
    """Identify the stored curve by its provenance, independently of the current run."""
    origin = case.get('baseline_origin') or {}
    indicator = origin.get('version') or origin.get('date')
    if not indicator and origin.get('git_commit'):
        indicator = 'rev '+origin['git_commit'][:7]
    return 'pyBLOSSUM reference'+(f' ({indicator})' if indicator else '')


def draw_case(path, case, datasets):
    from matplotlib import pyplot as plt
    fig, (axis, errors) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True,
                                      gridspec_kw={'height_ratios': [2, 1]}, layout='constrained')
    colors = {'regression': '#6b4c9a', 'reference': '#b66a12'}
    current_x, current_y = [], []
    for data in datasets:
        name, v, stored, actual = data['comparison'], data['velocity'], data['stored'], data['actual']
        label = pyblossum_reference_label(case) if name == 'regression' else 'Workbook reference'
        axis.plot(v, stored, linestyle='--' if name == 'regression' else 'none',
                  marker=None if name == 'regression' else '.', markersize=3,
                  color=colors[name], label=label)
        if actual is not None:
            current_x.extend(v); current_y.extend(actual)
            errors.plot(v, 100*(actual-stored)/stored, color=colors[name], label=f'{label} error')
            tol = data['tolerance']
            limit = 100*(tol['rtol']+tol['atol_cm']/stored)
            errors.fill_between(v, -limit, limit, color=colors[name], alpha=.08)
    if current_x:
        x, indexes = np.unique(current_x, return_index=True)
        axis.plot(x, np.asarray(current_y)[indexes], color='#156294', linewidth=1.5, label='Current code')
    else:
        axis.text(.5, .5, 'Current calculation failed. See report for details.', transform=axis.transAxes, ha='center')
    angle = case.get('inputs', {}).get('angle', '?')
    statuses = '; '.join(f"{entry['comparison'].capitalize()}: {entry['status']}" for entry in case['comparisons'])
    angle_label = f'requested impact angle {angle} deg'
    fig.suptitle(f"{case['id']}\n{case.get('model', 'Unknown model')}, {angle_label}\n{statuses}", fontsize=11)
    axis.set_ylabel('Projectile diameter (cm)')
    ymax = None
    if current_x:
        try:
            ymax = overlay_ymax(case['model'], case['normalized_inputs'])
        except (ValueError, KeyError, RuntimeError) as exc:
            case['plot_scaling_warning'] = f'Automatic scaling: HVI calculation failed: {exc}'
    axis.set_ylim(bottom=0, top=ymax)
    axis.legend(fontsize=8)
    errors.axhline(0, color='gray', linewidth=.6)
    errors.set_ylabel('Signed error (%)')
    errors.set_xlabel('Velocity (km/s)')
    if current_x:
        errors.legend(fontsize=8)
    for ax in (axis, errors):
        ax.grid(alpha=.2)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def write_html(path, report):
    rows, details = [], []
    escape = html.escape
    for case in report['cases']:
        plot = f"<a href='{escape(case['plot'])}'>Overlay</a>" if case.get('plot') else ''
        for comparison in case['comparisons']:
            maximum = comparison.get('max_relative_error_pct')
            rms = comparison.get('rms_relative_error_pct')
            rows.append('<tr>'+''.join([
                f"<td>{escape(case['id'])}</td><td>{comparison['comparison']}</td>",
                f"<td class='{comparison['status']}'>{comparison['status']}</td>",
                f"<td>{comparison.get('points', '')}</td>",
                f"<td>{maximum:.6g}</td>" if maximum is not None else '<td></td>',
                f"<td>{rms:.6g}</td>" if rms is not None else '<td></td>',
                f"<td>{comparison.get('failed_points', '')}</td><td>{plot}</td>",
                f"<td>{escape(comparison.get('message', ''))}</td>",
            ])+'</tr>')
        details.append(f"<details><summary>{escape(case['id'])}: inputs and provenance</summary><pre>{escape(json.dumps(case, indent=2))}</pre></details>")
    counts = report['counts']
    path.write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<title>pyBLOSSUM curve validation</title><style>
body{font:15px system-ui,sans-serif;margin:32px;color:#233044}table{border-collapse:collapse;width:100%}
th,td{padding:8px;border-bottom:1px solid #d8dce2;text-align:left;vertical-align:top}th{background:#edf1f5}
.FAIL,.ERROR{color:#b42318;font-weight:600}.PASS{color:#22613d}pre{white-space:pre-wrap;font-size:12px}
details{margin:12px 0}a{color:#156294}</style><h1>pyBLOSSUM curve validation</h1>'''
        + f"<p>{counts['PASS']} passed, {counts['FAIL']} failed, {counts['ERROR']} errors. {len(report['cases'])} cases.</p>"
        + '<p>Configurations come from cases.json. Regression compares with the saved pyBLOSSUM reference curve; reference compares with the independent XLSX reference curve. Plot labels identify the reference revision. Commit snapshots are cached automatically; tracked baseline files and workbooks are unchanged. Shaded plot bands show the pointwise acceptance limits.</p>'
        + f"<p>Workbook source: {escape(report['metadata']['workbook_source'])}. <a href='summary.csv'>Summary CSV</a> / <a href='report.json'>Full JSON report</a>.</p>"
        + '<table><thead><tr><th>Case</th><th>Comparison</th><th>Status</th><th>Points</th><th>Max error (%)</th><th>RMS error (%)</th><th>Failed points</th><th>Plot</th><th>Message</th></tr></thead><tbody>'
        + ''.join(rows)+'</tbody></table><h2>Inputs, tolerances, and sources</h2>'+''.join(details)+'</html>', encoding='utf-8')


def export_commit_curves(directory, commit, bootstrap):
    """Worker entry point: executed in an isolated copy of the committed models."""
    directory = Path(directory)
    manifest = json.loads((ROOT/'validation/cases.json').read_bytes())
    if manifest['schema_version'] != 2:
        raise ValueError('Unsupported committed validation manifest schema')
    baselines = read_baselines(ROOT/'validation'/manifest['baseline_file'])
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['case_id', 'velocity_km_s', 'diameter_cm'])
    cases = {}
    for filename, spec in manifest['workbooks'].items():
        for column, raw in spec['cases'].items():
            case_id = f'{Path(filename).stem}_{column}'
            velocities, _ = baselines.curve(case_id, raw['baseline_points'])
            inputs = normalize_inputs(raw['inputs'], raw['units'])
            model = resolve_model(spec.get('models_by_column', {}).get(column, spec.get('model')), inputs)
            actual = calculate(model, inputs, velocities)
            writer.writerows((case_id, float(v), float(d)) for v, d in zip(velocities, actual))
            cases[case_id] = {'inputs': raw['inputs'], 'units': raw['units'], 'model': model,
                              'baseline_points': len(velocities)}
    if not cases:
        raise ValueError('No committed cases to capture')
    blob = buffer.getvalue().encode('utf-8')
    (directory/'curves.csv').write_bytes(blob)
    metadata = {'schema_version': 1, 'git_commit': commit,
                'captured_utc': datetime.now(timezone.utc).isoformat(),
                'bootstrap_configurations': bootstrap, 'cases': cases,
                'curves_sha256': hashlib.sha256(blob).hexdigest(),
                'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
                'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted((ROOT/'BLEs').glob('*.py'))}}
    (directory/'snapshot.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')


def ensure_commit_snapshot(repo_root, commit, manifest_path):
    """Cache historical models by commit and any inputs borrowed from the working tree."""
    git = ['git', '-C', str(repo_root)]
    committed_manifest = subprocess.run(
        [*git, 'ls-tree', '--name-only', commit, '--', 'validation/cases.json'],
        capture_output=True, check=True,
    ).stdout
    bootstrap = not committed_manifest
    cache_key = commit
    bootstrap_hashes = None
    if bootstrap:
        manifest_blob = manifest_path.read_bytes()
    else:
        manifest_blob = subprocess.run(
            [*git, 'show', f'{commit}:validation/cases.json'], capture_output=True, check=True,
        ).stdout
    baseline_name = json.loads(manifest_blob)['baseline_file']
    if Path(baseline_name).name != baseline_name:
        raise ValueError('baseline_file must be a filename for commit snapshots')
    if bootstrap:
        baseline_blob = (manifest_path.parent/baseline_name).read_bytes()
        bootstrap_hashes = {
            'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
            'baseline_sha256': hashlib.sha256(baseline_blob).hexdigest(),
        }
        key = json.dumps({'commit': commit, **bootstrap_hashes}, sort_keys=True)
        cache_key = 'bootstrap-'+hashlib.sha256(key.encode()).hexdigest()
    cache = repo_root/'validation/reports/baselines'/cache_key

    def read_snapshot():
        metadata = json.loads((cache/'snapshot.json').read_bytes())
        if (metadata['git_commit'] != commit
                or metadata.get('bootstrap_inputs') != bootstrap_hashes
                or hashlib.sha256((cache/'curves.csv').read_bytes()).hexdigest() != metadata['curves_sha256']):
            raise ValueError(f'Invalid commit snapshot: {cache}')
        return cache, metadata

    if cache.exists():
        return read_snapshot()
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Staging and publication share a filesystem; failed workers never publish a snapshot.
    with tempfile.TemporaryDirectory(prefix='capture_', dir=cache.parent) as tmp:
        staging = Path(tmp)
        source = staging/'source'
        validation = source/'validation'
        validation.mkdir(parents=True)
        archive = subprocess.run([*git, 'archive', '--format=zip', commit, '--', 'BLEs'],
                                 capture_output=True, check=True).stdout
        with zipfile.ZipFile(io.BytesIO(archive)) as entries:
            for name in entries.namelist():
                if name.startswith('BLEs/') and name.endswith('.py'):
                    relative = Path(name)
                    if '..' in relative.parts:
                        raise ValueError('Invalid source archive path')
                    target = source/relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(entries.read(name))
        (validation/'cases.json').write_bytes(manifest_blob)
        if not bootstrap:
            baseline_blob = subprocess.run(
                [*git, 'show', f'{commit}:validation/{baseline_name}'], capture_output=True, check=True,
            ).stdout
        (validation/baseline_name).write_bytes(baseline_blob)
        # Use today's reader/adapter with the historical model implementations.
        runner = validation/'validate_curves.py'
        runner.write_bytes(Path(__file__).read_bytes())
        result = staging/'result'
        result.mkdir()
        script = "import runpy,sys; ns=runpy.run_path(sys.argv[1]); ns['export_commit_curves'](sys.argv[2],sys.argv[3],sys.argv[4]=='1')"
        worker = subprocess.run([sys.executable, '-B', '-c', script, str(runner), str(result), commit, '1' if bootstrap else '0'],
                                cwd=source, capture_output=True, text=True)
        if worker.returncode:
            raise ValueError(f'Cannot capture commit {commit[:7]}:\n{worker.stderr[-6000:]}')
        if bootstrap:
            metadata_path = result/'snapshot.json'
            metadata = json.loads(metadata_path.read_bytes())
            metadata['bootstrap_inputs'] = bootstrap_hashes
            metadata_path.write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
        # Directory rename publishes complete curves and metadata together.
        try:
            result.rename(cache)
        except OSError:
            # Another run has already published this snapshot.
            if not cache.is_dir():
                raise
    return read_snapshot()


def automatic_baseline(repo_root, manifest_path):
    head = git_commit(repo_root, 'HEAD')
    changed = subprocess.run(['git', '-C', str(repo_root), 'diff', '--name-only', 'HEAD', '--',
                              'BLEs', 'validation/cases.json'], capture_output=True, text=True, check=True).stdout.strip()
    untracked = subprocess.run(['git', '-C', str(repo_root), 'ls-files', '--others', '--exclude-standard', '--',
                                'BLEs', 'validation/cases.json'], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(changed or untracked)
    # Inspect the commit header so a shallow clone is not mistaken for a root commit.
    header = subprocess.run(['git', '-C', str(repo_root), 'cat-file', 'commit', head],
                            capture_output=True, check=True).stdout.split(b'\n\n', 1)[0]
    parents = [line.split()[1].decode('ascii') for line in header.splitlines() if line.startswith(b'parent ')]
    reference = head if dirty or not parents else parents[0]
    # Capture HEAD too, so the next commit can immediately reuse it.
    cache, metadata = ensure_commit_snapshot(repo_root, head, manifest_path)
    if reference != head:
        cache, metadata = ensure_commit_snapshot(repo_root, reference, manifest_path)
    return cache/'curves.csv', metadata, dirty


def capture_baseline(*, repo_root=ROOT, label=None):
    """Explicitly advance all stored curves after calculating every case successfully."""
    repo_root = Path(repo_root).resolve()
    directory = repo_root/'validation'
    manifest_path = directory/'cases.json'
    original_manifest = manifest_path.read_bytes()
    manifest = json.loads(original_manifest)
    if manifest['schema_version'] != 2:
        raise ValueError('Unsupported validation manifest schema')
    baseline_path = directory/manifest['baseline_file']
    original_baseline = baseline_path.read_bytes()
    baselines = read_baselines(baseline_path)
    captured = datetime.now(timezone.utc).isoformat()
    try:
        commit = git_commit(repo_root, 'HEAD')
        dirty = subprocess.run(['git', '-C', str(repo_root), 'status', '--porcelain'],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit, dirty = None, 'Git metadata unavailable'
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((repo_root/'BLEs').glob('*.py'))}
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['case_id', 'velocity_km_s', 'diameter_cm'])
    registered = set()
    for filename, spec in manifest['workbooks'].items():
        for column, raw in spec['cases'].items():
            case_id = f'{Path(filename).stem}_{column}'
            registered.add(case_id)
            velocities, _ = baselines.curve(case_id, raw['baseline_points'])
            inputs = normalize_inputs(raw['inputs'], raw['units'])
            model = resolve_model(spec.get('models_by_column', {}).get(column, spec.get('model')), inputs)
            actual = calculate(model, inputs, velocities)
            writer.writerows((case_id, float(v), float(d)) for v, d in zip(velocities, actual))
            raw['baseline_origin'] = {
                'date': captured[:10], 'captured_utc': captured, 'git_commit': commit,
                'working_tree_status': dirty, 'code_sha256': code_hashes,
                'inputs': dict(raw['inputs']), 'units': dict(raw['units']), 'model': model}
            if label:
                raw['baseline_origin']['version'] = label
    if (set(baselines.points) | set(baselines.errors)) != registered:
        raise ValueError('Baseline cases do not match the manifest; no files were changed')
    if not registered:
        raise ValueError('No baseline cases; no files were changed')
    # Preserve both previous files before advancing either version-controlled file.
    archive = directory/'reports'/('baseline_before_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    archive.mkdir(parents=True, exist_ok=False)
    (archive/'cases.json').write_bytes(original_manifest)
    (archive/baseline_path.name).write_bytes(original_baseline)
    try:
        baseline_path.write_text(buffer.getvalue(), encoding='utf-8', newline='')
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    except OSError:
        baseline_path.write_bytes(original_baseline)
        manifest_path.write_bytes(original_manifest)
        raise
    return len(registered), archive


def run_validation(*, repo_root=ROOT, output_root=None, git_ref=None, selected=None,
                   comparison='both', plots=True, manifest_path=None, auto_baseline=False):
    repo_root = Path(repo_root).resolve()
    manifest_path = Path(manifest_path) if manifest_path else repo_root/'validation/cases.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest['schema_version'] != 2:
        raise ValueError('Unsupported validation manifest schema')
    specs = manifest['workbooks']
    registered_ids = set()
    for filename, spec in specs.items():
        for column, config in spec['cases'].items():
            if not re.fullmatch(r'[A-Z]+', column):
                raise ValueError(f'{filename}: invalid case column {column!r}')
            if not isinstance(config['inputs'], dict) or not isinstance(config['units'], dict):
                raise ValueError(f'{filename}/{column}: inputs and units must be objects')
            if not isinstance(config['baseline_points'], int) or config['baseline_points'] < 2:
                raise ValueError(f'{filename}/{column}: baseline_points must be at least two')
            registered_ids.add(f'{Path(filename).stem}_{column}')
    if selected:
        unknown = set(selected)-set(specs)
        if unknown:
            raise ValueError(f'Unknown workbook selection: {sorted(unknown)}')
    uses_reference = comparison != 'regression'
    uses_baselines = comparison != 'reference'
    commit = git_commit(repo_root, git_ref) if git_ref and uses_reference else None
    baseline_path = manifest_path.parent/manifest['baseline_file']
    snapshot, model_dirty = None, None
    if auto_baseline and uses_baselines:
        baseline_path, snapshot, model_dirty = automatic_baseline(repo_root, manifest_path)
    baselines = read_baselines(baseline_path) if uses_baselines else None
    output_root = Path(output_root) if output_root else repo_root/'validation'/'reports'
    output = output_root/('run_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True, exist_ok=False)
    try:
        code_commit = git_commit(repo_root, 'HEAD')
        dirty = subprocess.run(['git', '-C', str(repo_root), 'status', '--porcelain'], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        code_commit, dirty = None, 'Git metadata unavailable'
    report = {'metadata': {'generated_utc': datetime.now(timezone.utc).isoformat(),
                          'workbook_source': (f'git:{commit}' if commit else 'working-tree') if uses_reference else 'not read (regression only)',
                          'baseline_file': manifest['baseline_file'],
                          'baseline_sha256': baselines.sha256 if baselines else None,
                          'baseline_snapshot': snapshot,
                          'uncommitted_model_or_configuration_changes': model_dirty,
                          'code_commit': code_commit, 'working_tree_status': dirty,
                          'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
                          'matplotlib': version('matplotlib'),
                          'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                          'validation_tool_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),)},
                          'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((repo_root/'BLEs').glob('*.py'))}},
              'cases': []}

    def error_case(case_id, filename, message, kind='workbook'):
        return {'id': case_id, 'workbook': filename, 'comparisons': [
            {'comparison': kind, 'status': 'ERROR', 'message': str(message)}]}

    if not selected and baselines:
        for extra in sorted((set(baselines.points) | set(baselines.errors))-registered_ids):
            report['cases'].append(error_case(extra, '', 'CSV baseline case is not registered in cases.json: '+str(baselines.errors.get(extra, '')), kind='regression'))

    if not selected and uses_reference:
        if commit:
            names = subprocess.run(['git', '-C', str(repo_root), 'ls-tree', '-r', '--name-only', commit, '--', 'validation'], capture_output=True, text=True, check=True).stdout.splitlines()
            actual_files = {Path(n).name for n in names if n.endswith('.xlsx')}
        else:
            actual_files = {p.name for p in (repo_root/'validation').glob('*.xlsx') if not p.name.startswith('~$')}
        for extra in sorted(actual_files-set(specs)):
            report['cases'].append(error_case(extra, extra, 'Workbook is not registered in validation/cases.json'))

    for filename, spec in specs.items():
        if selected and filename not in selected:
            continue
        table, digest, reference_error = None, None, None
        if uses_reference:
            try:
                blob = workbook_bytes(repo_root/'validation'/filename, repo_root, commit)
                digest = hashlib.sha256(blob).hexdigest()
                table = read_workbook(blob)['reference']
            except (OSError, ValueError, KeyError, BadZipFile, ParseError, subprocess.SubprocessError) as exc:
                reference_error = str(exc)
        for column, raw in spec['cases'].items():
            case_id = f'{Path(filename).stem}_{column}'
            case = {'id': case_id, 'workbook': filename, 'workbook_sha256': digest,
                    'inputs': raw['inputs'], 'input_units': raw['units'],
                    'baseline_origin': raw.get('baseline_origin'),
                    'notes': spec.get('notes', [])+spec.get('notes_by_column', {}).get(column, []),
                    'comparisons': []}
            if snapshot:
                saved = snapshot['cases'].get(case_id)
                case['baseline_origin'] = dict(saved or {}, git_commit=snapshot['git_commit'],
                                               captured_utc=snapshot['captured_utc'],
                                               bootstrap_configurations=snapshot['bootstrap_configurations'])
                if saved and (saved['inputs'] != raw['inputs'] or saved['units'] != raw['units']):
                    case['notes'].append('Configuration differs from the committed pyBLOSSUM reference; comparison includes input changes.')
            report['cases'].append(case)
            try:
                inputs = normalize_inputs(raw['inputs'], raw['units'])
                case['normalized_inputs'] = inputs
                model = spec.get('models_by_column', {}).get(column, spec.get('model'))
                case['model'] = resolve_model(model, inputs)
            except (ValueError, KeyError, TypeError) as exc:
                case['comparisons'].append({'comparison': 'inputs', 'status': 'ERROR', 'message': str(exc)})
                continue
            datasets = []
            for kind in ('regression', 'reference'):
                if comparison != 'both' and comparison != kind:
                    continue
                tolerance = spec.get(kind+'_tolerances_by_column', {}).get(column, spec.get(kind+'_tolerance', manifest['tolerances'][kind]))
                entry = {'comparison': kind, 'tolerance': tolerance}
                case['comparisons'].append(entry)
                try:
                    check_tolerance(tolerance)
                    if kind == 'regression':
                        count = snapshot['cases'].get(case_id, {}).get('baseline_points', raw['baseline_points']) if snapshot else raw['baseline_points']
                        velocities, expected = baselines.curve(case_id, count)
                        rows = baselines.source_rows[case_id]
                        entry['source'] = {'file': str(baseline_path), 'case_id': case_id,
                                           'first_csv_row': min(rows), 'last_csv_row': max(rows)}
                    else:
                        if reference_error:
                            raise WorkbookError(reference_error)
                        x_col, y_col = spec.get('reference_pairs', {}).get(column, ['B', column])
                        header = spec['reference_header_row']
                        x_label = str(table.get(f'{x_col}{header}', '')).lower()
                        if not ('veloc' in x_label or x_label.startswith('v (')):
                            raise WorkbookError(f'{table.name}!{x_col}{header}: expected velocity header, got {x_label!r}')
                        velocities, expected = table.curve(x_col, y_col, header)
                        entry['source'] = {'sheet': table.name, 'x_column': x_col, 'y_column': y_col,
                                           'first_row': header+1, 'last_row': header+len(velocities)}
                    actual = None
                    try:
                        actual = calculate(case['model'], inputs, velocities)
                        entry.update(compare(actual, expected, tolerance))
                    except (ValueError, KeyError, TypeError, ArithmeticError, RuntimeError) as exc:
                        entry.update(status='ERROR', points=int(len(expected)), message=f'Model calculation: {exc}')
                    entry['csv'] = f'{case_id}_{kind}.csv'
                    write_points(output/entry['csv'], velocities, expected, actual, tolerance)
                    datasets.append({'comparison': kind, 'velocity': velocities, 'stored': expected,
                                     'actual': actual, 'tolerance': tolerance})
                except (ValueError, KeyError, TypeError) as exc:
                    entry.update(status='ERROR', message=str(exc))
            if plots and datasets:
                case['plot'] = f'{case_id}.png'
                draw_case(output/case['plot'], case, datasets)

    entries = [dict(case=case['id'], workbook=case['workbook'], **entry)
               for case in report['cases'] for entry in case['comparisons']]
    if not entries:
        missing = error_case('coverage', '', 'No validation cases were executed')
        report['cases'].append(missing)
        entries = [dict(case=missing['id'], workbook='', **missing['comparisons'][0])]
    report['counts'] = {status: sum(e['status'] == status for e in entries) for status in ('PASS', 'FAIL', 'ERROR')}
    report['exit_code'] = 0 if all(e['status'] == 'PASS' for e in entries) else 1
    (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    fields = ['case', 'workbook', 'comparison', 'status', 'points', 'failed_points',
              'max_abs_error_cm', 'rms_error_cm', 'max_relative_error_pct', 'rms_relative_error_pct', 'message']
    with (output/'summary.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(entries)
    write_html(output/'index.html', report)
    return report, output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git-ref', help='Explicitly read workbooks from this Git commit/ref, while testing current Python code')
    parser.add_argument('--workbook', action='append', help='Workbook filename or stem; repeat to select several')
    parser.add_argument('--comparison', choices=['both', 'regression', 'reference'], default='both')
    parser.add_argument('--output-dir', type=Path, help='Parent directory for a new timestamped report directory')
    parser.add_argument('--no-plots', action='store_true', help='Write CSV, JSON, and HTML without PNG plots')
    parser.add_argument('--capture-baseline', action='store_true', help='Explicitly replace all pyBLOSSUM reference curves with current results before a code update')
    parser.add_argument('--label', help='Optional version or descriptive label for --capture-baseline; otherwise use the capture date')
    args = parser.parse_args(argv)
    if args.capture_baseline:
        if args.git_ref or args.workbook or args.output_dir or args.no_plots or args.comparison != 'both':
            parser.error('--capture-baseline cannot be combined with validation options')
        try:
            count, archive = capture_baseline(label=args.label)
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RuntimeError) as exc:
            parser.exit(2, f'Baseline capture failed: {exc}\n')
        print(f'Captured {count} pyBLOSSUM reference curves. Previous baseline: {archive}')
        return 0
    if args.label:
        parser.error('--label requires --capture-baseline')
    selected = [name if name.endswith('.xlsx') else name+'.xlsx' for name in args.workbook] if args.workbook else None
    try:
        report, output = run_validation(output_root=args.output_dir, git_ref=args.git_ref,
                                        selected=selected, comparison=args.comparison, plots=not args.no_plots,
                                        auto_baseline=True)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Validation configuration error: {exc}\n')
    print('Curve validation:', ', '.join(f'{count} {status}' for status, count in report['counts'].items()))
    for case in report['cases']:
        for entry in case['comparisons']:
            if entry['status'] != 'PASS':
                detail = entry.get('message') or f"max error {entry['max_relative_error_pct']:.4g}% ({entry['failed_points']} failed points)"
                print(f"{entry['status']} {case['id']} {entry['comparison']}: {detail}")
    print(f'Report: {output/"index.html"}')
    return report['exit_code']


if __name__ == '__main__':
    sys.exit(main())
