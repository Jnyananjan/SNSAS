/**
 * ==============================================================================
 * Smart RFID Attendance System - Google Sheets Sync & Webhook Receiver
 * ==============================================================================
 */

// Replace with your actual Supabase URL and anon public key from Project Settings -> API
const SUPABASE_URL = "YOUR_SUPABASE_URL"; // e.g. "https://xyzproject.supabase.co"
const SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY";

function onOpen() {
  SpreadsheetApp.getUi().createMenu("🎓 Smart Attendance")
    .addItem("⚡ Clean Sync Now from Supabase", "syncNow")
    .addItem("⏱️ Enable Background Auto-Sync (Every 1 min)", "enableAutoSync")
    .addItem("⏹️ Disable Background Auto-Sync", "disableAutoSync")
    .addToUi();
}

/**
 * Clean Pull Sync: Fetches all records from Supabase and rebuilds clean rows
 */
function syncNow() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  ensureHeaders(sheet);

  try {
    const endpoint = SUPABASE_URL + "/rest/v1/attendance_logs?select=id,date,scanned_at,status,device_id,students(enroll_id,name,class_group)&order=scanned_at.asc";
    const response = UrlFetchApp.fetch(endpoint, {
      method: "get",
      headers: {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": "Bearer " + SUPABASE_ANON_KEY
      },
      muteHttpExceptions: true
    });

    if (response.getResponseCode() !== 200) {
      SpreadsheetApp.getUi().alert("Supabase Error (" + response.getResponseCode() + "): " + response.getContentText());
      return;
    }

    const logs = JSON.parse(response.getContentText());
    if (!logs || logs.length === 0) {
      SpreadsheetApp.getUi().alert("No attendance records found in Supabase.");
      return;
    }

    // Clean up any old or malformed rows below header
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.deleteRows(2, lastRow - 1);
    }

    // Rebuild clean rows with verified student names & enroll IDs
    logs.forEach(log => {
      const student = log.students || {};
      const enrollId = student.enroll_id || "N/A";
      const studentName = student.name || "Unknown";
      const classGroup = student.class_group || "";
      const scanTime = formatTimestamp(log.scanned_at);

      sheet.appendRow([
        scanTime,
        enrollId,
        studentName,
        classGroup,
        log.status || "PRESENT",
        log.device_id || "TERMINAL_01",
        log.id
      ]);

      const newRow = sheet.getLastRow();
      styleRow(sheet, newRow, log.status);
    });

    SpreadsheetApp.getActiveSpreadsheet().toast(`Synced ${logs.length} clean record(s) from Supabase!`, "Sync Complete", 4);
  } catch (err) {
    SpreadsheetApp.getUi().alert("Sync Failed: " + err.toString());
  }
}

/**
 * Webhook receiver for real-time push from Supabase Webhooks
 */
function doPost(e) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    ensureHeaders(sheet);

    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput('{"result":"no_data"}');
    }

    let record = JSON.parse(e.postData.contents);
    if (record.record) record = record.record; // Supabase webhook envelope

    // Fetch full student name and enroll_id if not present
    if (!record.name && record.student_id) {
      record = fetchStudentDetails(record);
    }

    const scanTime = record.scanned_at ? formatTimestamp(record.scanned_at) : Utilities.formatDate(new Date(), "GMT+5:30", "yyyy-MM-dd HH:mm:ss");
    sheet.appendRow([
      scanTime,
      record.enroll_id || record.student_id || "N/A",
      record.name || "Student",
      record.class_group || "",
      record.status || "PRESENT",
      record.device_id || "TERMINAL_01",
      record.id || ""
    ]);

    const newRow = sheet.getLastRow();
    styleRow(sheet, newRow, record.status || "PRESENT");

    return ContentService.createTextOutput(JSON.stringify({ result: "success" })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ result: "error", message: err.toString() }));
  }
}

function ensureHeaders(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["Scan Time", "Enroll ID", "Student Name", "Class / Section", "Status", "Terminal", "Record ID"]);
    const headerRange = sheet.getRange(1, 1, 1, 7);
    headerRange.setFontWeight("bold");
    headerRange.setBackground("#1F497D");
    headerRange.setFontColor("#FFFFFF");
    headerRange.setHorizontalAlignment("center");
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 170);
    sheet.setColumnWidth(2, 110);
    sheet.setColumnWidth(3, 180);
    sheet.setColumnWidth(4, 130);
    sheet.setColumnWidth(5, 110);
    sheet.setColumnWidth(6, 120);
    sheet.hideColumns(7);
  }
}

function formatTimestamp(isoStr) {
  if (!isoStr) return Utilities.formatDate(new Date(), "GMT+5:30", "yyyy-MM-dd HH:mm:ss");
  try {
    const d = new Date(isoStr);
    return Utilities.formatDate(d, "GMT+5:30", "yyyy-MM-dd HH:mm:ss");
  } catch (e) {
    return String(isoStr);
  }
}

function styleRow(sheet, rowIdx, status) {
  const cell = sheet.getRange(rowIdx, 5);
  cell.setFontWeight("bold").setHorizontalAlignment("center");
  if (status === "PRESENT") {
    cell.setBackground("#D9EAD3").setFontColor("#274E13");
  } else {
    cell.setBackground("#FFF2CC").setFontColor("#7F6000");
  }
}

function fetchStudentDetails(record) {
  try {
    const url = SUPABASE_URL + "/rest/v1/students?id=eq." + record.student_id + "&select=enroll_id,name,class_group";
    const resp = UrlFetchApp.fetch(url, {
      method: "get",
      headers: { "apikey": SUPABASE_ANON_KEY, "Authorization": "Bearer " + SUPABASE_ANON_KEY },
      muteHttpExceptions: true
    });
    if (resp.getResponseCode() === 200) {
      const items = JSON.parse(resp.getContentText());
      if (items && items.length > 0) {
        return {
          id: record.id,
          scanned_at: record.scanned_at,
          status: record.status,
          device_id: record.device_id,
          enroll_id: items[0].enroll_id,
          name: items[0].name,
          class_group: items[0].class_group
        };
      }
    }
  } catch (e) {
    Logger.log("Fetch student error: " + e);
  }
  return record;
}

function enableAutoSync() {
  disableAutoSync();
  ScriptApp.newTrigger("syncNow").timeBased().everyMinutes(1).create();
  SpreadsheetApp.getUi().alert("✅ Background Auto-Sync Enabled! (Syncs every 1 min)");
}

function disableAutoSync() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "syncNow") ScriptApp.deleteTrigger(t);
  });
  SpreadsheetApp.getUi().alert("⏹️ Background Auto-Sync Disabled.");
}
