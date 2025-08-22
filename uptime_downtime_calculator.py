#!/usr/bin/env python3

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

import run_pipeline

def merge_time_windows(windows: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not windows:
        return []
    windows_sorted = sorted(windows, key=lambda w: w[0])
    merged: List[Tuple[datetime, datetime]] = []
    cur_start, cur_end = windows_sorted[0]
    for start, end in windows_sorted[1:]:
        if start <= cur_end:
            if end > cur_end:
                cur_end = end
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged

def clamp_interval(interval: Tuple[datetime, datetime], bounds: Tuple[datetime, datetime]) -> Tuple[datetime, datetime]:
    start, end = interval
    b_start, b_end = bounds
    clamped_start = max(start, b_start)
    clamped_end = min(end, b_end)
    if clamped_start >= clamped_end:
        return None
    return (clamped_start, clamped_end)

def get_business_windows_for_range(store_id: str, start_utc: datetime, end_utc: datetime) -> List[Tuple[datetime, datetime]]:
    windows: List[Tuple[datetime, datetime]] = []
    date_cursor = start_utc.date()
    while date_cursor <= end_utc.date():
        day_windows = run_pipeline.business_lookup.get(store_id, {}).get(date_cursor, [])
        for w in day_windows:
            clamped = clamp_interval(w, (start_utc, end_utc))
            if clamped:
                windows.append(clamped)
        date_cursor = date_cursor + timedelta(days=1)
    return merge_time_windows(windows)

def get_observation_before(store_id: str, target_time: datetime):
    store_obs = run_pipeline.observations.get(store_id, [])
    last = None
    for ts, status in store_obs:
        if ts < target_time:
            last = (ts, status)
        else:
            break
    return last

def get_observations_in_range(store_id: str, start_utc: datetime, end_utc: datetime):
    store_obs = run_pipeline.observations.get(store_id, [])
    result = []
    for ts, status in store_obs:
        if ts < start_utc:
            continue
        if ts > end_utc:
            break
        result.append((ts, status))
    return result

def compute_uptime_downtime_for_store(store_id: str, start_utc: datetime, end_utc: datetime) -> Dict[str, float]:
    business_windows = get_business_windows_for_range(store_id, start_utc, end_utc)
    if not business_windows:
        return {"uptime_s": 0.0, "downtime_s": 0.0}

    uptime_s = 0.0
    downtime_s = 0.0

    for win_start, win_end in business_windows:
        prev_obs = get_observation_before(store_id, win_start)
        current_status = prev_obs[1] if prev_obs else 'inactive'
        current_time = win_start

        obs = get_observations_in_range(store_id, win_start, win_end)
        for ts, status in obs:
            interval_s = (ts - current_time).total_seconds()
            if interval_s > 0:
                if current_status == 'active':
                    uptime_s += interval_s
                else:
                    downtime_s += interval_s
            current_time = ts
            current_status = status

        tail_s = (win_end - current_time).total_seconds()
        if tail_s > 0:
            if current_status == 'active':
                uptime_s += tail_s
            else:
                downtime_s += tail_s

    return {"uptime_s": uptime_s, "downtime_s": downtime_s}

def main():
    ref_time = run_pipeline.df_status['timestamp_utc'].max()

    ranges = {
        'last_hour': (ref_time - timedelta(hours=1), ref_time),
        'last_day': (ref_time - timedelta(days=1), ref_time),
        'last_week': (ref_time - timedelta(days=7), ref_time),
    }

    rows = []
    for store_id in run_pipeline.observations.keys():
        record = {"store_id": store_id}
        for label, (start_utc, end_utc) in ranges.items():
            metrics = compute_uptime_downtime_for_store(store_id, start_utc, end_utc)
            total = metrics['uptime_s'] + metrics['downtime_s']
            uptime_pct = (metrics['uptime_s'] / total * 100.0) if total > 0 else 0.0
            record[f"{label}_uptime_s"] = round(metrics['uptime_s'], 2)
            record[f"{label}_downtime_s"] = round(metrics['downtime_s'], 2)
            record[f"{label}_uptime_pct"] = round(uptime_pct, 2)
        rows.append(record)
        if len(rows) % 500 == 0:
            print(f"Processed {len(rows):,} stores for uptime/downtime...")

    report_df = pd.DataFrame(rows)
    report_df.to_csv('uptime_report.csv', index=False)

    summary = {
        'reference_time': str(ref_time),
        'num_stores': len(rows),
        'columns': list(report_df.columns),
    }
    with open('uptime_report.json', 'w') as f:
        json.dump({
            'summary': summary,
            'sample_rows': report_df.head(5).to_dict(orient='records')
        }, f, indent=2)

    print("✅ Uptime/downtime reports generated:")
    print("  - uptime_report.csv")
    print("  - uptime_report.json")

if __name__ == "__main__":
    main()