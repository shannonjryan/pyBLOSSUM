"""Shared output paths and configuration CSV format for BLE runs."""

import csv
from datetime import datetime
from itertools import count
from pathlib import Path


# These units describe values as entered, before model-specific conversions.
CONFIG_UNITS = {
    'proj_mat': '-', 'bumper_mat': '-', 'wall_mat': '-', 'target_mat': '-',
    'outerBumper_mat': '-', 'innerBumper_mat': '-', 'type': '-', 'mode': '-',
    'angle': 'deg',
    'proj_density': 'g/cm3', 'bumper_density': 'g/cm3', 'wall_density': 'g/cm3',
    'shield_density': 'g/cm3', 'foam_density': 'g/cm3',
    'outerBumper_density': 'g/cm3', 'innerBumper_density': 'g/cm3',
    'thickness': 'cm', 'bumper_thick': 'cm', 'wall_thick': 'cm',
    'shield_thick': 'cm', 'outerBumper_thick': 'cm', 'innerBumper_thick': 'cm',
    'standoff': 'cm', 'standoff1': 'cm', 'standoff2': 'cm', 'S_MLI': 'cm',
    'max_damage': 'cm',
    'wall_yield': 'MPa', 'shield_HB': 'HB', 'shield_C': 'km/s',
    'bumper_AD': 'g/cm2', 'wall_AD': 'g/cm2', 'mesh_AD': 'g/cm2',
    'kevlar_AD': 'g/cm2', 'nextel_AD': 'g/cm2', 'AD_MLI': 'g/cm2',
    'MLI_AD': 'g/cm2', 'SP_AD': 'g/cm2', 'foam_AD': 'g/cm2', 'SP_mass': 'g',
}


def create_run_directory(root):
    """Create a fresh timestamped results folder and return its filename timestamp."""
    now = datetime.now()
    name = f"run_{now:%Y%m%d_%H%M%S_%f}"
    results = Path(root) / 'results'
    results.mkdir(parents=True, exist_ok=True)
    for attempt in count():
        folder = results / (name if attempt == 0 else f'{name}_{attempt}')
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        return folder, f"{now:%Y%m%d_%H%M%S}"


def write_config_csv(config, path, *, input_file=None):
    """Write headers, units, and the original configuration values."""
    extra_units = {}
    if input_file is not None and any(column not in CONFIG_UNITS for column in config.columns):
        with open(input_file, encoding='utf-8-sig', newline='') as source:
            rows = csv.reader(source)
            headers = next(rows, ())
            extra_units = dict(zip(headers, next(rows, ())))
    units = [CONFIG_UNITS.get(column, extra_units.get(column, '')) for column in config.columns]
    with path.open('w', encoding='utf-8', newline='') as output:
        writer = csv.writer(output, lineterminator='\n')
        writer.writerow(config.columns)
        writer.writerow(units)
        config.to_csv(output, index=False, header=False, lineterminator='\n')
