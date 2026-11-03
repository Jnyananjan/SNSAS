-- ==============================================================================
-- 01_schema.sql: Smart RFID Student Attendance Database Schema
-- Supabase / PostgreSQL
-- ==============================================================================

-- 1. Students Table
CREATE TABLE IF NOT EXISTS public.students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enroll_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    rfid_uid TEXT NOT NULL UNIQUE,
    class_group TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- Case-insensitive index for fast RFID UID lookups
CREATE INDEX IF NOT EXISTS idx_students_rfid_uid ON public.students (UPPER(rfid_uid));

-- 2. Devices Table (Attendance Terminals)
CREATE TABLE IF NOT EXISTS public.devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_seen TIMESTAMPTZ DEFAULT timezone('utc', now())
);

-- 3. Attendance Logs Table
CREATE TABLE IF NOT EXISTS public.attendance_logs (
    id BIGSERIAL PRIMARY KEY,
    student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    status TEXT NOT NULL DEFAULT 'PRESENT', -- 'PRESENT', 'LATE'
    device_id TEXT REFERENCES public.devices(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    
    -- Hard safety constraint: strictly 1 attendance record per student per day
    CONSTRAINT unique_student_daily_attendance UNIQUE (student_id, date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON public.attendance_logs (date);
CREATE INDEX IF NOT EXISTS idx_attendance_student_id ON public.attendance_logs (student_id);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance_logs ENABLE ROW LEVEL SECURITY;

-- Anonymous users (e.g. terminals using anon key) can call RPC functions, 
-- but direct table updates are locked to authenticated service roles.
CREATE POLICY "Allow public read for active students" 
    ON public.students FOR SELECT 
    USING (is_active = true);

CREATE POLICY "Allow service role full access on students" 
    ON public.students FOR ALL 
    TO service_role 
    USING (true);

CREATE POLICY "Allow public read for attendance logs" 
    ON public.attendance_logs FOR SELECT 
    USING (true);

CREATE POLICY "Allow service role full access on attendance logs" 
    ON public.attendance_logs FOR ALL 
    TO service_role 
    USING (true);

