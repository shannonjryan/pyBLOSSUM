"""Lightweight startup and shared dependencies for analysis windows."""

from concurrent.futures import ThreadPoolExecutor
import csv
from functools import cache
from pathlib import Path
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication


@cache
def material_properties(root):
    """Read the small material table without importing the analysis stack."""
    columns = {
        'density': 'Density (g/ccm)',
        'hardness': 'Hardness (HB)',
        'yield': 'Yield strength (Mpa)',
        'tensile_modulus': 'Tensile modulus (Gpa)',
    }
    materials = {}
    with (Path(root) / 'data' / 'material_data.csv').open(encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source):
            materials.setdefault(row['Material'], {
                key: row[column] or 'nan' for key, column in columns.items()
            })
    return materials


def _load_analysis_libraries():
    import itertools
    import numpy as np
    import pandas as pd
    import seaborn as sns

    sns.set_theme()
    styles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1, 1)), (0, (3, 5, 1, 5, 1, 5))]
    return {
        'np': np,
        'pd': pd,
        'itertools': itertools,
        'color_line_style_pairs': list(zip(sns.color_palette(), styles)),
    }


@cache
def warm_analysis_libraries():
    """Start one background import and share its result across the Qt session."""
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='analysis-imports')
    future = executor.submit(_load_analysis_libraries)
    executor.shutdown(wait=False)
    return future


def run_standalone(window_type):
    app = QApplication(sys.argv)
    window = window_type()
    window.show()
    QTimer.singleShot(0, warm_analysis_libraries)
    return app.exec_()
