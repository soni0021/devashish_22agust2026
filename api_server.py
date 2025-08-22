#!/usr/bin/env python3
"""
FastAPI server for asynchronous uptime report generation.

Endpoints:
- POST /trigger_report    → Enqueue a report job, returns report_id
- GET  /get_report        → Poll job status or download CSV when complete
- GET  /health            → Health check
- GET  /reports/status    → List recent jobs (debug)

Implementation details:
- Uses SQLite (reports.db) to track jobs
- Runs report generation in a background thread
- Lazily imports heavy processing modules inside the background job
- Reuses uptime computation utilities from uptime_downtime_calculator
"""

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
import sqlite3
import uuid
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any

import pandas as pd


DB_PATH = 'reports.db'
REPORTS_DIR = 'reports'

app = FastAPI()


def init_db() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS report_jobs (
                report_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                file_path TEXT
            )
            '''
        )
        conn.commit()
    finally:
        conn.close()


def _update_job(report_id: str, updates: Dict[str, Any]) -> None:
    if not updates:
        return
    set_clause = ', '.join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values()) + [report_id]
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f'UPDATE report_jobs SET {set_clause} WHERE report_id=?', values)
        conn.commit()
    finally:
        conn.close()


def generate_report_background(report_id: str) -> None:
    """Background job: compute uptime report CSV and update job status."""
    try:
        _update_job(report_id, {"status": "Running"})

        # Lazy imports to avoid heavy work at server startup
        # Import inside thread so pipeline builds only when needed
        import importlib
        # Always reload modules so any changes in CSVs are picked up dynamically
        rp_mod = importlib.import_module('run_pipeline')
        run_pipeline = importlib.reload(rp_mod)
        up_mod = importlib.import_module('uptime_downtime_calculator')
        uptime_mod = importlib.reload(up_mod)
        # Ensure uptime module uses the freshly reloaded pipeline
        setattr(uptime_mod, 'run_pipeline', run_pipeline)

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
                metrics = uptime_mod.compute_uptime_downtime_for_store(store_id, start_utc, end_utc)
                # Convert seconds to appropriate units
                if label == 'last_hour':
                    record[f"uptime_{label}(in minutes)"] = round(metrics['uptime_s'] / 60, 2)
                    record[f"downtime_{label}(in minutes)"] = round(metrics['downtime_s'] / 60, 2)
                else:  # last_day and last_week
                    record[f"uptime_{label}(in hours)"] = round(metrics['uptime_s'] / 3600, 2)
                    record[f"downtime_{label}(in hours)"] = round(metrics['downtime_s'] / 3600, 2)
            rows.append(record)

        report_df = pd.DataFrame(rows)
        # Reorder columns as requested
        column_order = [
            'store_id',
            'uptime_last_hour(in minutes)',
            'uptime_last_day(in hours)',
            'uptime_last_week(in hours)',
            'downtime_last_hour(in minutes)',
            'downtime_last_day(in hours)',
            'downtime_last_week(in hours)'
        ]
        report_df = report_df[column_order]
        file_path = os.path.join(REPORTS_DIR, f'report_{report_id}.csv')
        report_df.to_csv(file_path, index=False)

        _update_job(report_id, {
            "status": "Complete",
            "completed_at": datetime.now().isoformat(),
            "file_path": file_path,
        })

    except Exception as exc:
        _update_job(report_id, {"status": "Failed"})
        # Log to stderr
        print(f"Report generation failed for {report_id}: {exc}")


@app.post('/trigger_report')
def trigger_report():
    """Trigger report generation and return a report_id."""
    try:
        report_id = str(uuid.uuid4())
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                'INSERT INTO report_jobs (report_id, status, created_at) VALUES (?, ?, ?)',
                (report_id, 'Queued', datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        thread = threading.Thread(target=generate_report_background, args=(report_id,), daemon=True)
        thread.start()

        return {
            'report_id': report_id,
            'message': 'Report generation started'
        }
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get('/get_report')
def get_report(report_id: str = Query(..., description="Report job ID")):
    """Get report status or download completed report as CSV."""
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.execute(
                'SELECT status, file_path, created_at, completed_at FROM report_jobs WHERE report_id=?',
                (report_id,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return JSONResponse({'error': 'Report not found'}, status_code=404)
                           
        status, file_path, created_at, completed_at = row
        if status == 'Complete' and file_path and os.path.exists(file_path):
            return FileResponse(
                file_path,
                media_type='text/csv',
                filename=f'uptime_report_{report_id}.csv'
            )

        return {
            'status': status,
            'created_at': created_at,
            'completed_at': completed_at
        }
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}


@app.get('/reports/status')
def list_reports():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute('SELECT report_id, status, created_at, completed_at, file_path FROM report_jobs ORDER BY created_at DESC LIMIT 10')
        rows = cursor.fetchall()
    finally:
        conn.close()

    return {
        'reports': [
            {
                'report_id': r[0],
                'status': r[1],
                'created_at': r[2],
                'completed_at': r[3],
                'file_path': r[4],
            } for r in rows
        ]
    }


@app.on_event('startup')
def on_startup() -> None:
    init_db()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api_server:app', host='0.0.0.0', port=5000, reload=False)

