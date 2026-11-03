"""
sheet_sync_worker.py: Safe Automated Spreadsheet Sync Worker
Monitors Supabase attendance records and maintains a synchronized, safe,
read-only Excel / CSV sheet for school staff without giving staff direct
write access to the database.
"""

import os
import sys
import time
import argparse
from datetime import date
from typing import Optional

from excel_exporter import fetch_and_export, create_attendance_workbook


def run_sync_loop(interval_sec: int = 10, target_date: Optional[str] = None):
    """Continuously syncs incoming scans into the safe spreadsheet."""
    if not target_date:
        target_date = str(date.today())

    output_file = f"attendance_live_{target_date}.xlsx"
    print("=" * 60)
    print("  Smart Attendance: Safe Spreadsheet Sync Worker")
    print(f"  Target Date: {target_date}")
    print(f"  Live Sheet:  {output_file}")
    print("  Database is the isolated, protected source of truth.")
    print("=" * 60)

    try:
        while True:
            fetch_and_export(target_date, output_file)
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\n[INFO] Sync worker stopped cleanly.")


def resync_from_database(target_date: Optional[str] = None):
    """
    Emergency or routine recovery:
    Rebuilds the entire spreadsheet from the master Supabase database,
    erasing any accidental formula or cell corruption made by staff.
    """
    if not target_date:
        target_date = str(date.today())

    output_file = f"attendance_live_{target_date}.xlsx"
    print(f"[RE-SYNC] Restoring '{output_file}' from authoritative Supabase records...")
    res = fetch_and_export(target_date, output_file)
    print(f"[RE-SYNC COMPLETE] Clean spreadsheet regenerated: {res}")
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Safe Spreadsheet Sync Worker")
    parser.add_argument("--resync", action="store_true", help="One-shot rebuild of spreadsheet from database")
    parser.add_argument("--date", type=str, default=str(date.today()), help="Date in YYYY-MM-DD format")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.resync:
        resync_from_database(args.date)
    else:
        run_sync_loop(interval_sec=args.interval, target_date=args.date)

