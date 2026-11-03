-- ==============================================================================
-- 02_attendance_rpc.sql: Atomic RPC Function for Smart Attendance
-- Supabase / PostgreSQL
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.record_daily_attendance(
    p_rfid_uid TEXT,
    p_device_id TEXT DEFAULT 'Room605'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_student RECORD;
    v_existing_log RECORD;
    v_now_ist TIMESTAMP := (now() AT TIME ZONE 'Asia/Kolkata');
    v_today DATE := v_now_ist::DATE;
    v_clean_uid TEXT := UPPER(TRIM(p_rfid_uid));
    v_target_device_id TEXT := NULL;
    v_time_str TEXT := to_char(v_now_ist, 'HH12:MI AM');
BEGIN
    -- 1. Find the student by RFID UID (case-insensitive)
    SELECT * INTO v_student
    FROM public.students
    WHERE UPPER(rfid_uid) = v_clean_uid AND is_active = true;

    -- If student does not exist or inactive
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'status', 'NO_DATA_FOUND',
            'name', 'Unknown Card',
            'enroll_id', v_clean_uid,
            'time', v_time_str,
            'message', 'No Data Found'
        );
    END IF;

    -- 2. Check if student has already scanned today
    SELECT id, scanned_at INTO v_existing_log
    FROM public.attendance_logs
    WHERE student_id = v_student.id AND date = v_today;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'status', 'ALREADY_MARKED',
            'enroll_id', v_student.enroll_id,
            'name', v_student.name,
            'first_scanned', to_char(v_existing_log.scanned_at AT TIME ZONE 'Asia/Kolkata', 'HH12:MI AM'),
            'time', v_time_str,
            'message', 'Already Marked'
        );
    END IF;

    -- 3. Auto-register device if provided (avoids FK constraint errors)
    IF p_device_id IS NOT NULL AND TRIM(p_device_id) <> '' THEN
        INSERT INTO public.devices (id, name, location, last_seen)
        VALUES (TRIM(p_device_id), TRIM(p_device_id), 'Classroom', now())
        ON CONFLICT (id) DO UPDATE SET last_seen = now();
        v_target_device_id := TRIM(p_device_id);
    END IF;

    -- 4. Insert new attendance record
    INSERT INTO public.attendance_logs (student_id, date, scanned_at, status, device_id)
    VALUES (v_student.id, v_today, now(), 'PRESENT', v_target_device_id);

    -- 5. Return success JSON
    RETURN jsonb_build_object(
        'status', 'MARKED',
        'enroll_id', v_student.enroll_id,
        'name', v_student.name,
        'scanned_at', v_time_str,
        'time', v_time_str,
        'message', 'Marked'
    );

EXCEPTION
    -- Catch race conditions / duplicate scans gracefully
    WHEN unique_violation THEN
        RETURN jsonb_build_object(
            'status', 'ALREADY_MARKED',
            'enroll_id', v_student.enroll_id,
            'name', v_student.name,
            'time', v_time_str,
            'message', 'Already Marked (Race Condition Handled)'
        );
END;
$$;

-- Grant execution permissions
GRANT EXECUTE ON FUNCTION public.record_daily_attendance(TEXT, TEXT) TO anon, authenticated, service_role;
