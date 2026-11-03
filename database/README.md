# Supabase Database Setup

Follow these steps to initialize your free database in under 2 minutes:

1. Create a free account at [Supabase](https://supabase.com) and create a new project.
2. In the left navigation menu, click **SQL Editor**.
3. Create a new query, paste the contents of `01_schema.sql`, and click **Run**.
4. Create another new query, paste the contents of `02_attendance_rpc.sql`, and click **Run**.
5. Go to **Project Settings -> API** to find:
   - **Project URL** (e.g., `https://xyzproject.supabase.co`)
   - **anon / public key** (Used in the ESP32 firmware)
   - **service_role key** (Used securely in the Python sync worker)

### Enrolling Students:
You can directly insert students in the Supabase **Table Editor** UI (looks like Excel):
- `student_id`: e.g. `STU001`
- `name`: e.g. `Alice Smith`
- `rfid_uid`: e.g. `3A5F22B1` (upper-case hex string reported by the reader)
- `class_group`: e.g. `Grade 10-A`
- `is_active`: `true`

