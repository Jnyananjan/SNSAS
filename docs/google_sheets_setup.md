# Google Sheets Real-Time Sync Setup

Connect your Supabase attendance records to a live Google Sheet in 60 seconds with no complex API keys, no Google Cloud Console setup, and zero billing.

---

## 1. Create Your Google Sheet
1. Open [Google Sheets](https://sheets.new) and create a new blank spreadsheet.
2. Name it **"Smart Attendance Register"**.

---

## 2. Add the Google Apps Script
1. In your Google Sheet, click **Extensions** in the top menu -> **Apps Script**.
2. Replace all code in the script editor with the code from [`google_sheets/Code.gs`](../google_sheets/Code.gs).
3. At the top of `Code.gs`, fill in your Supabase project credentials:
   ```javascript
   const SUPABASE_URL = "https://your-project.supabase.co";
   const SUPABASE_ANON_KEY = "your-public-anon-key";
   ```
4. Click the **Save** disk icon.

---

## 3. Deploy as a Web App (For Live Push)
1. Click the blue **Deploy** button at top right -> **New deployment**.
2. Click the gear icon ⚙️ next to "Select type" and select **Web app**.
3. Set:
   * **Description**: `Attendance Webhook`
   * **Execute as**: `Me (your email)`
   * **Who has access**: `Anyone`
4. Click **Deploy**, click **Authorize access**, select your Google account, and click **Allow**.
5. Copy the **Web App URL** (looks like `https://script.google.com/macros/s/.../exec`).

---

## 4. Connect Webhook in Supabase
1. In your [Supabase Dashboard](https://supabase.com), go to **Database -> Webhooks**.
2. Click **Create a new webhook**.
3. Set:
   * **Name**: `Google Sheets Push`
   * **Table**: `public.attendance_logs`
   * **Events**: `INSERT`
   * **Method**: `POST`
   * **URL**: Paste your Google Web App URL.
4. Click **Save Webhook**.

Whenever a card is tapped on the ESP32-S3 terminal, it will instantly appear in your Google Sheet within 1-2 seconds!

---

## 5. Sheet Features & Controls
When you refresh your Google Sheet, a custom menu **🎓 Smart Attendance** will appear:
* **⚡ Clean Sync Now from Supabase**: Purges blank or placeholder rows and rebuilds the sheet with verified student names, enroll IDs, and IST timestamps.
* **⏱️ Enable Background Auto-Sync (Every 1 min)**: Creates an automatic Google timer trigger to keep the sheet synchronized continuously.
