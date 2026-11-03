"""
excel_exporter.py: Daily Attendance Excel Report Generator
Pulls data from Supabase (or local dataset) and generates a formatted,
color-coded Excel workbook (.xlsx) for school staff and administrators.
"""

import os
import argparse
from datetime import date, datetime
from typing import List, Dict, Any, Optional

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    openpyxl = None


def create_attendance_workbook(
    report_date: str,
    students: List[Dict[str, Any]],
    attendance_records: List[Dict[str, Any]],
    output_path: str
) -> str:
    """
    Builds a beautifully styled multi-tab Excel workbook with summary statistics
    and an attendance sheet with color-coded PRESENT and ABSENT highlights.
    """
    if openpyxl is None:
        raise ImportError("openpyxl is required. Run: pip install openpyxl")

    wb = openpyxl.Workbook()

    # Style definitions
    font_title = Font(name="Calibri", size=16, bold=True, color="1F497D")
    font_section = Font(name="Calibri", size=12, bold=True, color="1F497D")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_normal = Font(name="Calibri", size=11)

    fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_present = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid") # Soft green
    fill_absent = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")  # Soft red
    fill_kpi = PatternFill(start_color="F2F4F8", end_color="F2F4F8", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="D3D3D3"),
        right=Side(style="thin", color="D3D3D3"),
        top=Side(style="thin", color="D3D3D3"),
        bottom=Side(style="thin", color="D3D3D3")
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # Map attendance logs by student_id
    attendance_by_id = {rec.get("student_id"): rec for rec in attendance_records}

    total_students = len(students)
    present_count = 0

    # -------------------------------------------------------------
    # Sheet 1: Daily Register
    # -------------------------------------------------------------
    ws_reg = wb.active
    ws_reg.title = "Daily Register"
    ws_reg.views.sheetView[0].showGridLines = True

    # Title Banner
    ws_reg["A1"] = f"STUDENT ATTENDANCE REGISTER - {report_date}"
    ws_reg["A1"].font = font_title
    ws_reg.row_dimensions[1].height = 30

    headers = ["Enroll ID", "Student Name", "Class / Section", "Status", "Check-in Time", "Device Terminal"]
    ws_reg.append([])  # Blank row 2
    ws_reg.append(headers)  # Row 3
    ws_reg.row_dimensions[3].height = 24

    for col_idx in range(1, len(headers) + 1):
        cell = ws_reg.cell(row=3, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center

    row_num = 4
    for stu in sorted(students, key=lambda s: s.get("enroll_id") or s.get("student_id", "")):
        s_id = stu.get("enroll_id") or stu.get("student_id")
        rec = attendance_by_id.get(s_id) or attendance_by_id.get(stu.get("id"))

        is_present = rec is not None and rec.get("status") in ("PRESENT", "LATE")
        if is_present:
            present_count += 1
            status_text = rec.get("status", "PRESENT")
            time_str = rec.get("scanned_at", "-")
            device_str = rec.get("device_id", "-")
            row_fill = fill_present
        else:
            status_text = "ABSENT"
            time_str = "-"
            device_str = "-"
            row_fill = fill_absent

        row_data = [
            stu.get("enroll_id") or stu.get("student_id", ""),
            stu.get("name", ""),
            stu.get("class_group", ""),
            status_text,
            time_str,
            device_str
        ]

        ws_reg.append(row_data)
        ws_reg.row_dimensions[row_num].height = 20

        for col_idx in range(1, len(headers) + 1):
            cell = ws_reg.cell(row=row_num, column=col_idx)
            cell.font = font_normal
            cell.border = thin_border
            if col_idx == 4:
                cell.fill = row_fill
                cell.alignment = align_center
                cell.font = font_bold
            elif col_idx in (1, 5, 6):
                cell.alignment = align_center
            else:
                cell.alignment = align_left

        row_num += 1

    # Auto-adjust column widths
    for col in ws_reg.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_reg.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------
    # Sheet 2: Executive Summary
    # -------------------------------------------------------------
    ws_sum = wb.create_sheet(title="Executive Summary")
    ws_sum.views.sheetView[0].showGridLines = True

    absent_count = total_students - present_count
    rate_pct = (present_count / total_students * 100) if total_students > 0 else 0.0

    ws_sum["A1"] = "ATTENDANCE EXECUTIVE SUMMARY"
    ws_sum["A1"].font = font_title
    ws_sum["A2"] = f"Report Date: {report_date}  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws_sum["A2"].font = font_normal

    kpis = [
        ("Total Enrolled Students", total_students),
        ("Present Today", present_count),
        ("Absent Today", absent_count),
        ("Attendance Rate", f"{rate_pct:.1f}%")
    ]

    ws_sum.append([])
    ws_sum.append(["Key Performance Metric", "Count / Rate"])
    header_row = 4
    for col_idx in (1, 2):
        c = ws_sum.cell(row=header_row, column=col_idx)
        c.font = font_header
        c.fill = fill_header
        c.alignment = align_center

    cur_row = 5
    for label, val in kpis:
        ws_sum.append([label, val])
        for col_idx in (1, 2):
            c = ws_sum.cell(row=cur_row, column=col_idx)
            c.font = font_bold
            c.border = thin_border
            c.fill = fill_kpi
            c.alignment = align_center if col_idx == 2 else align_left
        cur_row += 1

    for col in ws_sum.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_sum.column_dimensions[col_letter].width = max(max_len + 4, 20)

    # Save to disk
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path


def fetch_and_export(target_date: Optional[str] = None, output_file: Optional[str] = None) -> str:
    """Fetches real-time records from Supabase and saves the Excel report."""
    if not target_date:
        target_date = str(date.today())
    if not output_file:
        output_file = f"attendance_{target_date}.xlsx"

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        print("[WARN] SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Using sample mock data for demonstration.")
        students = [
            {"student_id": "STU101", "name": "Alice Smith", "class_group": "Grade 10-A"},
            {"student_id": "STU102", "name": "Bob Johnson", "class_group": "Grade 10-A"},
            {"student_id": "STU103", "name": "Charlie Davis", "class_group": "Grade 10-B"},
            {"student_id": "STU104", "name": "Diana Prince", "class_group": "Grade 10-B"},
        ]
        records = [
            {"student_id": "STU101", "status": "PRESENT", "scanned_at": "08:45:12", "device_id": "TERMINAL_01"},
            {"student_id": "STU103", "status": "PRESENT", "scanned_at": "08:50:01", "device_id": "TERMINAL_01"},
        ]
    else:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)

        stu_res = client.table("students").select("id, student_id, name, class_group").eq("is_active", True).execute()
        students = stu_res.data or []

        att_res = client.table("attendance_logs").select("student_id, status, scanned_at, device_id").eq("date", target_date).execute()
        records = att_res.data or []

    file_created = create_attendance_workbook(target_date, students, records, output_file)
    print(f"[SUCCESS] Attendance report saved to: {file_created}")
    return file_created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export daily attendance to a styled Excel report.")
    parser.add_argument("--date", type=str, default=str(date.today()), help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--output", type=str, default="", help="Output .xlsx file path")
    args = parser.parse_args()

    out = args.output if args.output else f"attendance_{args.date}.xlsx"
    fetch_and_export(args.date, out)

