# Rechecking the validation curves

Activate the pyBLOSSUM environment and run from the repository root:

```console
python -B validation/validate_curves.py
```

The default reads configurations from `cases.json`, automatically captures and
reuses Git-commit snapshots, and reads independent reference curves from the
working-tree XLSX files. It performs two separate comparisons:

- **Regression:** current results against the previous committed pyBLOSSUM curve.
- **Reference:** current results against the workbook's `reference` curve, using
  the same JSON configuration. This can expose differences in rounded
  material properties, input metadata, or equation implementations. These
  reference values include programmed calculations and digitized publication
  curves; they are not all experimental measurements.

The JSON file defines 44 configurations across nine workbook families. The CSV
contains their 6,600 regression points. Selecting both comparison types gives
88 comparisons. Missing baselines, incorrect point counts, duplicate velocities,
unregistered CSV cases or workbooks, missing reference points, Excel errors,
and failed model calculations produce errors rather than being skipped.

## Data layout

No separate capture step is needed. A normal validation run caches curves for
HEAD and the required reference commit under `reports/baselines/<full-commit>/`.
Existing snapshots are reused without recalculating them. Committed models are
evaluated in an isolated subprocess using the active Python environment.

- With uncommitted model or configuration changes, the reference is HEAD.
- With those files matching HEAD, the reference is HEAD's first parent.
- A root commit has no predecessor, so it compares against itself.

Only changes under `BLEs/` or to `validation/cases.json` select the uncommitted
comparison; generated reports and documentation edits do not. Each snapshot
records its commit, inputs, units, models, code hashes, and runtime versions.
The plot label identifies the reference commit. Configuration changes are
included in the comparison and noted in the report. Added cases without a
predecessor produce a missing-baseline error.

For commits predating `cases.json`, the runner uses the current JSON
configurations and CSV velocity grids with that commit's model code. The
snapshot directory is keyed by a hash of the commit and inputs, and the report records
both source hashes under `bootstrap_inputs`. Commits containing the validation
files use their own saved configurations.
Missing Git history or a failed historical calculation is reported as an error;
the runner does not silently substitute current results. A snapshot is only
published after all its calculations succeed.

Automatic capture does not modify tracked CSV/JSON files or the independent
XLSX references. Deleting the ignored snapshot cache causes it to be rebuilt
from Git on the next run. Reference-only validation does not create snapshots.

- `cases.json`: configurations, original input units, model selection, expected
  baseline point counts, tolerance definitions, reference ranges, and import
  provenance.
- `baselines.csv`: historical curves and velocity grids used to seed commit
  snapshots and fixed numerical tests. Case IDs combine workbook stem and case
  key, e.g. `whipple_C`.
- `*.xlsx`: reference data only. The redundant `pyBLOSSUM` and `BLC` sheets have
  been removed. Existing reference worksheets and hidden reference metadata are
  preserved.
- `tests/`: targeted numerical, integration, and validation-runner tests.
- `reports/`: generated reports and commit snapshots, excluded from Git.

The migration preserved the original configuration values, units, and baseline
numbers without correcting known metadata discrepancies or regenerating curves.
Import provenance records the original workbook hash and Python-sheet range.
Regression-only checks do not read Excel files. Reference-only checks do not
read the CSV baselines.

The existing single-point functions are used for models without an array API.
The Whipple cases use the new array functions and their checked scalar numerical
solvers. The runner does not change equations, infer missing velocities, or
interpolate/extrapolate a reference onto a different velocity grid. Instead, it
evaluates current code directly at each comparison's stored velocities.

The JSC Whipple and Reimerdes Whipple solvers report an error if the
hypervelocity equation has no valid diameter on either side of the switch
at a standoff-to-diameter ratio of 30.

## Output

Every run creates a separate `validation/reports/run_<timestamp>/` directory:

- `index.html`: summary table, links to plots/data, and expandable input and
  provenance records.
- `<case>.png`: curve overlay and signed relative-error panel. The plot title
  includes each comparison's status, including missing-reference errors.
  The diameter axis runs from zero to twice the current diameter at the exact
  HVI transition. Single-wall and transparent models use automatic scaling
  because their equations have no HVI transition.
  The historical curve is labelled `pyBLOSSUM reference` with the source revision
  from the case's `baseline_origin.git_commit`. Optional `baseline_origin.version`
  or `baseline_origin.date` (YYYY-MM-DD) takes precedence when recorded. These
  identify the stored curve's source, not the date of the current validation run.
- `<case>_<comparison>.csv`: velocity, expected/current diameter, errors,
  allowed error, and pointwise status. A failed calculation leaves current
  values blank rather than writing zeros.
- `summary.csv`: one row per comparison, with maximum/RMS errors and failed
  point counts.
- `report.json`: complete results, raw and normalized input values, unit labels,
  tolerance reasons, CSV row ranges, reference cell ranges, baseline/workbook
  hashes, code hashes, Git
  metadata, and Python/NumPy/SciPy versions. The timestamp is recorded in UTC.

Validation never edits the JSON configurations, CSV baselines, or workbooks.
If Excel
formulas have no saved cached values, open the workbook in Excel, recalculate,
and save it before rerunning. The script does not run Excel or require it to be
installed. Cached values are read through the standard-library XLSX/XML reader;
there is no new package dependency.

Exit codes are **0** for all comparisons passing, **1** for numerical failures
or data/model errors, and **2** for a command/configuration error. A nonzero
result identifies a numerical discrepancy or an input/configuration problem.

## Useful selections

```console
python -B validation/validate_curves.py --workbook whipple
python -B validation/validate_curves.py --workbook singleWall --workbook transparent
python -B validation/validate_curves.py --comparison regression
python -B validation/validate_curves.py --comparison reference --no-plots
python -B validation/validate_curves.py --output-dir path/to/report-parent
python -B validation/validate_curves.py --git-ref HEAD
```

`--git-ref` explicitly reads reference workbook bytes from the requested commit.
Code, `cases.json`, and `baselines.csv` still come from the current checkout.
The resolved commit is
recorded in the report. The default never silently substitutes committed files
for unreadable or modified working-tree files. This option is useful for
reference comparisons and cloud-only/locked working copies. Older workbook
versions that still contain Python/BLC sheets are supported; only the reference
sheet is read. This option is unused for regression-only checks.

## Tolerances

A point passes when:

```text
abs(current - stored) <= atol_cm + rtol * abs(stored)
```

Every point must pass for the comparison to pass. Maximum relative error and
RMS relative error are reported as percentages. Absolute errors and absolute
tolerances are in centimetres. RMS statistics are unweighted over the stored
points; digitized curves may have uneven velocity spacing.

The versioned defaults in `cases.json` are:

| Comparison | Relative tolerance | Absolute tolerance | Basis |
| --- | ---: | ---: | --- |
| CSV baseline | 0.0001% | 1e-9 cm | Floating-point rounding |
| CSV baseline, Whipple cases | 0.15% | 1e-6 cm | Previously measured changes from tighter checked SLSQP solves |
| Workbook reference | 1% | 1e-6 cm | Rounded material properties and unit conversions |
| Digitized Enhanced MLI reference, C-E | 5% | 0.002 cm | Screen-read curves; provisional digitization limits |

These tolerances quantify numerical agreement, not BLE physical uncertainty or
statistical confidence. Each tolerance has a documented rationale in the
manifest. The targeted unit suite uses stricter tolerances for equivalent
implementations and independent numerical roots.

## Investigating a failure

1. Inspect the overlay and error panel, then the failed rows in its CSV.
2. Check the raw configuration, unit labels, normalized inputs, and source ranges
   in the report. Yield strength is converted from MPa to ksi when its label
   specifies MPa; single-wall sound speed is converted from m/s to km/s when
   needed. Units come from the JSON configuration. Unknown conversion units are
   errors. Other input values are used as stored, and known questionable labels
   are noted in the manifest.
3. Distinguish a code regression from reference rounding, digitization, a
   different source configuration, or incorrect migrated input metadata. For example,
   the original mesh D/E metadata stored angles in the `AD_MLI` row while its
   `angle` row remained zero. The runner applies no correction to those inputs.
4. Check the model's applicable angle limits and transition behavior using the
   targeted tests. Existing clipping remains part of the model.
5. Correct the identified code, configuration, or reference issue, then rerun
   both checks. Baselines are not regenerated by the validator.

## Adding a workbook or case

Register the reference workbook in `cases.json` with its model/dispatch name,
reference header row, and a `cases` object. Each case key identifies its default
reference diameter column, such as `C`; each case defines `inputs`, `units`, and
`baseline_points`. Most reference tables use velocity column B. Use
`reference_pairs` for different mappings, as in Enhanced MLI. Add the matching
case ID and its expected curve points to `baselines.csv`. CSV values are read
at full floating-point precision; expected counts and unique velocities are
checked explicitly.

New model families require a registered callable in `validation/validate_curves.py`.
Per-workbook or per-column tolerance overrides require a reason. Expected
regression curves come from the CSV and reference curves come from the XLSX
files. The fixture under `tests/fixtures` provides additional targeted scenarios
that are separate from the 44 validation configurations.

## Automated checks

```console
python -B -m unittest discover -s validation/tests -v
```

The suite covers solver failures, transition boundaries, MLI configurations,
scalar/array equivalence, GUI and CLI integration, workbook reading, and report
generation. Temporary directories and in-memory workbook fixtures isolate
test outputs from the reference files. Tests assert numerical results and
optimizer-call counts rather than machine-dependent timing thresholds.

