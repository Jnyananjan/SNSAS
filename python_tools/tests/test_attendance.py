"""
Unit tests for Smart RFID Attendance System
Verifies Excel workbook generation, duplicate protection, and student status.
"""

import os
import sys
import tempfile
import pytest
import openpyxl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from excel_exporter import create_attendance_workbook
from gsheet_sync_worker import push_to_google_sheet


@pytest.fixture
def sample_students():
    return [
        {"enroll_id": "STU001", "name": "Alice Green", "class_group": "Grade 10-A"},
        {"enroll_id": "STU002", "name": "Bob Stone", "class_group": "Grade 10-A"},
        {"enroll_id": "STU003", "name": "Charlie Red", "class_group": "Grade 10-B"},
    ]


@pytest.fixture
def sample_attendance():
    return [
        {"enroll_id": "STU001", "student_id": "STU001", "status": "PRESENT", "scanned_at": "08:30:15", "device_id": "TERMINAL_01"},
    ]


def test_excel_workbook_creation(sample_students, sample_attendance):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        out_path = create_attendance_workbook("2026-10-30", sample_students, sample_attendance, tmp_path)
        assert os.path.exists(out_path)

        wb = openpyxl.load_workbook(out_path)
        assert "Daily Register" in wb.sheetnames
        assert "Executive Summary" in wb.sheetnames

        ws_reg = wb["Daily Register"]
        # Verify headers in Row 3
        headers = [ws_reg.cell(row=3, column=c).value for c in range(1, 7)]
        assert headers == ["Enroll ID", "Student Name", "Class / Section", "Status", "Check-in Time", "Device Terminal"]

        # Row 4 (Alice - STU001) should be PRESENT
        assert ws_reg.cell(row=4, column=1).value == "STU001"
        assert ws_reg.cell(row=4, column=4).value == "PRESENT"
        assert ws_reg.cell(row=4, column=5).value == "08:30:15"

        # Row 5 (Bob - STU002) should be ABSENT
        assert ws_reg.cell(row=5, column=1).value == "STU002"
        assert ws_reg.cell(row=5, column=4).value == "ABSENT"

        # Summary KPIs verification
        ws_sum = wb["Executive Summary"]
        assert ws_sum.cell(row=5, column=2).value == 3  # Total Enrolled
        assert ws_sum.cell(row=6, column=2).value == 1  # Present
        assert ws_sum.cell(row=7, column=2).value == 2  # Absent
        assert ws_sum.cell(row=8, column=2).value == "33.3%"  # Attendance Rate

        wb.close()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_google_sheet_mock_payload():
    """Verify that push_to_google_sheet returns True when URL is unset (mock mode)."""
    payload = {
        "student_id": "STU101",
        "name": "Alice Green",
        "class_group": "Grade 10-A",
        "status": "PRESENT",
        "scanned_at": "09:00:00",
        "device_id": "TERMINAL_01"
    }
    assert push_to_google_sheet(payload) is True


def test_duplicate_prevention_logic():
    """Verify that multiple scans for the same student id resolve to a single present status."""
    students = [{"student_id": "STU001", "name": "Alice", "class_group": "10-A"}]
    # Simulate duplicate scan event
    duplicate_records = [
        {"student_id": "STU001", "status": "PRESENT", "scanned_at": "08:30:00", "device_id": "TERMINAL_01"},
        {"student_id": "STU001", "status": "PRESENT", "scanned_at": "08:30:05", "device_id": "TERMINAL_01"},
    ]

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        create_attendance_workbook("2026-10-30", students, duplicate_records, tmp_path)
        wb = openpyxl.load_workbook(tmp_path)
        ws_sum = wb["Executive Summary"]
        assert ws_sum.cell(row=5, column=2).value == 1  # 1 student
        assert ws_sum.cell(row=6, column=2).value == 1  # Still 1 present, not 2
        wb.close()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_google_sheet_mock_payload():
    """Verify that push_to_google_sheet returns True when URL is unset (mock mode)."""
    payload = {
        "student_id": "STU101",
        "name": "Alice Green",
        "class_group": "Grade 10-A",
        "status": "PRESENT",
        "scanned_at": "09:00:00",
        "device_id": "TERMINAL_01"
    }
    assert push_to_google_sheet(payload) is True
