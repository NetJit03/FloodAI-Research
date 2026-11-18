#!/usr/bin/env python3
"""Build a per-SAR-chip location/date manifest for Sen1Floods11 + Phimai.

This does NOT fetch rainfall or infer a precise SAR acquisition time from a date.
Use the CSV output to audit all train/valid/test/Bolivia records before joining
30-minute IMERG precipitation by geolocation and actual UTC acquisition time.

Run from project root:
  python build_sen1_weather_manifest.py
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import rasterio
from rasterio.warp import transform as transform_points

SPLITS = ('train', 'valid', 'test', 'bolivia')
# The hand-labeled chip prefix 'Mekong' refers to the Cambodia event.
EVENT_NAME_MAP = {'Mekong': 'Cambodia'}


def find_metadata(root: Path) -> Path:
    options = [
        root / 'metadata' / 'Sen1Floods11_Metadata.geojson',
        root / 'Sen1Floods11_Metadata.geojson',
    ]
    for candidate in options:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        'Cannot locate event metadata. Tried: ' + ', '.join(map(str, options)))


def date_to_iso(value: str) -> str:
    text = str(value).strip().replace('/', '-')
    try:
        return datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError as exc:
        raise ValueError(f'Unexpected s1_date: {value!r}') from exc


def read_metadata(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    features = data.get('features', [])
    by_location = {}
    for feature in features:
        prop = feature.get('properties') or {}
        location = prop.get('location')
        if not location:
            raise ValueError(f'Event without a location property: {prop}')
        if location in by_location:
            raise ValueError(f'Duplicate metadata event name: {location}')
        by_location[location] = prop
    return by_location


def center_and_bounds(path: Path):
    # Only inspect geospatial metadata; do not load the 512x512 image array.
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f'Missing CRS in {path}')
        bounds = src.bounds
        xc = (bounds.left + bounds.right) / 2
        yc = (bounds.bottom + bounds.top) / 2
        xs, ys = transform_points(src.crs, 'EPSG:4326', [xc], [yc])
        lon, lat = float(xs[0]), float(ys[0])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(
                f'Invalid chip coordinates for {path}: {lon}, {lat}')
        return lon, lat


def build_row(root: Path, split: str, sar_name: str, label_name: str, meta: dict):
    sar_file = root / 'S1Hand' / sar_name
    label_file = root / 'LabelHand' / label_name
    if not sar_file.is_file():
        raise FileNotFoundError(f'Missing Sentinel-1 image: {sar_file}')
    if not label_file.is_file():
        raise FileNotFoundError(f'Missing label: {label_file}')
    if not sar_name.endswith('_S1Hand.tif') or not label_name.endswith('_LabelHand.tif'):
        raise ValueError(f'Unexpected names: {sar_name!r}, {label_name!r}')
    image_id = sar_name.removesuffix('_S1Hand.tif')
    if image_id != label_name.removesuffix('_LabelHand.tif'):
        raise ValueError(f'SAR/label mismatch: {sar_name!r} / {label_name!r}')

    chip_event = image_id.split('_')[0]
    event_name = EVENT_NAME_MAP.get(chip_event, chip_event)
    if event_name not in meta:
        raise ValueError(
            f'Missing metadata for chip event {chip_event!r} -> {event_name!r}')
    info = meta[event_name]
    lon, lat = center_and_bounds(sar_file)
    return dict(
        image_id=image_id,
        split=split,
        dataset_event=chip_event,
        metadata_event=event_name,
        metadata_event_id=str(info.get('ID', '')),
        sar_date_utc=date_to_iso(info['s1_date']),
        # Must be verified from source scene metadata.
        sar_datetime_utc='',
        time_status='needs_exact_utc_time',
        orbit_direction=str(info.get('orbit', '')),
        relative_orbit=str(info.get('rel_orbit_num', '')),
        longitude=f'{lon:.7f}',
        latitude=f'{lat:.7f}',
        sar_file=str(sar_file),
        label_file=str(label_file),
        rain24_mm='',
        rain72_mm='',
        rain168_mm='',
        rain_status='not_downloaded',
    )


def read_records(root: Path, meta: dict):
    result = []
    all_ids = set()
    for split in SPLITS:
        split_file = root / 'splits' / f'flood_{split}_data.csv'
        if not split_file.is_file():
            raise FileNotFoundError(f'Missing split CSV: {split_file}')
        with split_file.open(newline='', encoding='utf-8-sig') as f:
            for row_number, record in enumerate(csv.reader(f), start=1):
                if not record or not any(cell.strip() for cell in record):
                    continue
                if len(record) < 2:
                    raise ValueError(
                        f'Invalid row {row_number} in {split_file}')
                sar_name, label_name = record[0].strip(), record[1].strip()
                row = build_row(root, split, sar_name, label_name, meta)
                if row['image_id'] in all_ids:
                    raise ValueError(
                        f'Duplicate chip across splits: {row["image_id"]}')
                all_ids.add(row['image_id'])
                result.append(row)
    return result


def phimai_pilot(base: Path):
    sar_file = base / 'sar' / 'Thailand_S1_VV_VH_Sigma0dB.tif'
    if not sar_file.is_file():
        print(
            f'INFO: Thailand pilot file not found at {sar_file}; skipping optional row.')
        return None
    lon, lat = center_and_bounds(sar_file)
    return dict(
        image_id='Thailand_Phimai_20211005',
        split='thailand_diagnostic_pilot',
        dataset_event='Phimai_2021',
        metadata_event='Thailand',
        metadata_event_id='TH_PHIMAI_20211005',
        sar_date_utc='2021-10-05',
        # Previously verified S1B source product.
        sar_datetime_utc='2021-10-05T11:20:44Z',
        time_status='verified_scene_start_utc',
        orbit_direction='',
        relative_orbit='',
        longitude=f'{lon:.7f}',
        latitude=f'{lat:.7f}',
        sar_file=str(sar_file),
        label_file=str(base / 'masks' / 'thailand_flood_reference.tif'),
        rain24_mm='', rain72_mm='', rain168_mm='',
        rain_status='not_downloaded',
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, default=Path('data/sen1floods11'))
    p.add_argument('--thailand-root', type=Path,
                   default=Path('data/thailand_external/2021_10_05'))
    p.add_argument('--output', type=Path,
                   default=Path('data/weather/sar_weather_manifest.csv'))
    args = p.parse_args()
    meta_path = find_metadata(args.data_root)
    meta = read_metadata(meta_path)
    rows = read_records(args.data_root, meta)
    active = {row['metadata_event'] for row in rows}
    unused = sorted(set(meta) - active)
    unknown = sorted(active - set(meta))
    if unknown:
        raise RuntimeError(f'Events lacking metadata: {unknown}')
    thailand = phimai_pilot(args.thailand_root)
    if thailand is not None:
        rows.append(thailand)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        'image_id', 'split', 'dataset_event', 'metadata_event', 'metadata_event_id',
        'sar_date_utc', 'sar_datetime_utc', 'time_status', 'orbit_direction',
        'relative_orbit', 'longitude', 'latitude', 'sar_file', 'label_file',
        'rain24_mm', 'rain72_mm', 'rain168_mm', 'rain_status',
    ]
    with args.output.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    print('Event metadata entries:', len(meta))
    print('Active events in hand-labeled splits:',
          len(active), ', '.join(sorted(active)))
    print('Metadata events not used in these splits:', unused)
    print('Dataset-prefix mapping: Mekong -> Cambodia')
    print('Split counts:', dict(Counter(r['split'] for r in rows)))
    print('Total rows:', len(rows))
    print('Rainfall populated:', sum(
        bool(r['rain24_mm']) for r in rows), '(expected zero at this stage)')
    print('Exact acquisition time populated:', sum(
        bool(r['sar_datetime_utc']) for r in rows))
    print('Saved:', args.output)
    print('NEXT: verify exact UTC SAR time for each event/chip before extracting IMERG 24/72/168-hour sums.')


if __name__ == '__main__':
    main()
