# Python Tools: Safe Spreadsheet & Attendance Reports

This folder contains Python utilities for synchronizing attendance from the Supabase database into a safe, formatted Excel (.xlsx) / CSV spreadsheet.

## Key Concept: Safe Read-Only Isolation
- **Supabase** is the authoritative master database.
- **The Spreadsheet** is a read-only mirror distributed to teachers, staff, and management.
- If a staff member accidentally deletes a row, alters a cell, or breaks a formula in the spreadsheet, **no data in Supabase is damaged**.
- Running `--resync` instantly restores the spreadsheet from the database.

## Installation

```bash
cd python_tools
pip install -r requirements.txt
```

Create your `.env` file (copied from `.env.example`):
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
```

## Usage

### 1. Generate Daily Attendance Excel (.xlsx)
Generates an Excel workbook with a **Daily Register** tab (present/absent highlighted in soft green/red) and an **Executive Summary** KPI tab:
```bash
python excel_exporter.py --date 2026-10-30
```

### 2. Live Safe Spreadsheet Sync Worker
Runs in the background, listening or polling for new scans and writing them live to `attendance_live_YYYY-MM-DD.xlsx`:
```bash
python sheet_sync_worker.py --interval 10
```

### 3. Emergency One-Shot Rebuild (`--resync`)
If someone modifies or corrupts the shared spreadsheet, run:
```bash
python sheet_sync_worker.py --resync
```
This pulls all authoritative records from Supabase and regenerates a fresh spreadsheet in 1 second.

### 4. Running Tests
```bash
pytest tests/ -v
```

