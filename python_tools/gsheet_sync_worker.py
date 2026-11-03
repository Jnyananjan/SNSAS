"""
gsheet_sync_worker.py: Real-Time Supabase to Google Sheets Sync Worker
Polls or listens to Supabase attendance records and forwards them live to a
Google Sheet via a lightweight Google Apps Script Webhook.
"""

import os
import sys
import time
import argparse
from datetime import date
from typing import Set, Optional
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
GOOGLE_SHEET_WEBHOOK_URL = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "")


def push_to_google_sheet(record: dict) -> bool:
    """Sends a single attendance row payload to the Google Sheet webhook."""
    id_label = record.get("enroll_id") or record.get("student_id", "")
    if not GOOGLE_SHEET_WEBHOOK_URL:
        print(f"[MOCK GOOGLE SHEET] (Set GOOGLE_SHEET_WEBHOOK_URL in .env) -> Row: {record['name']} ({id_label})")
        return True

    try:
        resp = requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=record, timeout=8)
        if resp.status_code == 200:
            print(f"[GOOGLE SHEET SYNCED] -> {record['name']} ({id_label}) at {record.get('scanned_at', '')}")
            return True
        else:
            print(f"[GOOGLE SHEET ERROR] HTTP {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[GOOGLE SHEET EXCEPTION] Failed to send: {e}")
        return False


def run_gsheet_sync(interval_sec: int = 4, target_date: Optional[str] = None):
    """Continuously monitors Supabase and pushes new scans to Google Sheets."""
    if not target_date:
        target_date = str(date.today())

    print("=" * 65)
    print("  Real-Time Supabase -> Google Sheets Sync Worker")
    print(f"  Target Date: {target_date}")
    print(f"  Poll Interval: {interval_sec} seconds")
    print("  Master database (Supabase) is isolated and secure.")
    print("=" * 65)

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[ERROR] SUPABASE_URL or SUPABASE_SERVICE_KEY not configured in .env!")
        print("Please configure .env before starting the sync worker.")
        sys.exit(1)

    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    synced_log_ids: Set[int] = set()

    # Pre-populate already existing logs for today so we only push new incoming ones
    try:
        init_res = client.table("attendance_logs").select("id").eq("date", target_date).execute()
        for item in (init_res.data or []):
            synced_log_ids.add(item["id"])
        print(f"[READY] Monitoring for new check-ins... ({len(synced_log_ids)} records already in database)")
    except Exception as err:
        print(f"[WARN] Could not fetch initial state: {err}")

    while True:
        try:
            # Query attendance logs joined with student profile
            res = (
                client.table("attendance_logs")
                .select("id, scanned_at, status, device_id, students(enroll_id, name, class_group)")
                .eq("date", target_date)
                .order("id")
                .execute()
            )

            records = res.data or []
            for item in records:
                log_id = item["id"]
                if log_id not in synced_log_ids:
                    student_info = item.get("students") or {}
                    enroll_id = student_info.get("enroll_id") or student_info.get("student_id", "UNKNOWN")
                    payload = {
                        "log_id": log_id,
                        "enroll_id": enroll_id,
                        "student_id": enroll_id,
                        "name": student_info.get("name", "Unknown Student"),
                        "class_group": student_info.get("class_group", ""),
                        "status": item.get("status", "PRESENT"),
                        "scanned_at": str(item.get("scanned_at", "")),
                        "device_id": item.get("device_id", "TERMINAL_01")
                    }

                    success = push_to_google_sheet(payload)
                    if success:
                        synced_log_ids.add(log_id)

        except Exception as e:
            print(f"[SYNC LOOP WARN] Polling failed: {e}")

        time.sleep(interval_sec)


def resync_all_today(target_date: Optional[str] = None):
    """Pushes all of today's records to Google Sheets in bulk."""
    if not target_date:
        target_date = str(date.today())

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[ERROR] SUPABASE_URL or SUPABASE_SERVICE_KEY missing in .env.")
        return

    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    print(f"[RE-SYNC] Fetching all records for {target_date} from Supabase...")
    res = (
        client.table("attendance_logs")
        .select("id, scanned_at, status, device_id, students(enroll_id, name, class_group)")
        .eq("date", target_date)
        .order("id")
        .execute()
    )

    records = res.data or []
    print(f"[RE-SYNC] Found {len(records)} records. Forwarding to Google Sheet...")
    for item in records:
        student_info = item.get("students") or {}
        enroll_id = student_info.get("enroll_id") or student_info.get("student_id", "UNKNOWN")
        payload = {
            "log_id": item["id"],
            "enroll_id": enroll_id,
            "student_id": enroll_id,
            "name": student_info.get("name", "Unknown Student"),
            "class_group": student_info.get("class_group", ""),
            "status": item.get("status", "PRESENT"),
            "scanned_at": str(item.get("scanned_at", "")),
            "device_id": item.get("device_id", "TERMINAL_01")
        }
        push_to_google_sheet(payload)

    print("[RE-SYNC COMPLETE] All records refreshed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Supabase to Google Sheets Sync Worker")
    parser.add_argument("--resync", action="store_true", help="Re-push all today's records to Google Sheet")
    parser.add_argument("--date", type=str, default=str(date.today()), help="Date in YYYY-MM-DD format")
    parser.add_argument("--interval", type=int, default=3, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.resync:
        resync_all_today(args.date)
    else:
        run_gsheet_sync(interval_sec=args.interval, target_date=args.date)

