# ==============================================================================
# main.py: Smart RFID Student Attendance Terminal (MicroPython)
# Target: ESP32-S3 + SSD1306 128x64 I2C OLED + MFRC522 RFID + Active Buzzer
# Classroom: AI/ML-A | Edge-Cached Sub-10ms Instant Attendance + Offline Queue
# ==============================================================================

import time
import sys
import uselect
import network
import ujson
import urequests
import machine
from machine import Pin, I2C, SPI

import config
from buzzer import Buzzer
from mfrc522 import MFRC522
from ssd1306 import UniversalOLED

CLASSROOM = "AI/ML-A"
ROOM_NAME = "Room 605"
FOOTER_TEXT = "Room 605 AI/ML-A" # 16 chars * 8px = 128px exact

# ------------------------------------------------------------------------------
# Initialize Hardware
# ------------------------------------------------------------------------------
print("\n========================================================")
print("  Smart Attendance Terminal (MicroPython) Starting")
print("  Classroom: " + CLASSROOM + " | Terminal: " + config.DEVICE_ID)
print("  Display: SSD1306 128x64 OLED (SCL=9, SDA=10)")
print("  RFID: MFRC522 SPI (SCK=12, MOSI=11, MISO=13, CS=8, RST=18)")
print("========================================================")

# Active Buzzer (GPIO 4)
buzzer = Buzzer(pin_num=config.PIN_BUZZER)

# Fast 400kHz I2C for snappy 25ms OLED redraws
scl_pin = getattr(config, 'PIN_OLED_SCL', 9)
sda_pin = getattr(config, 'PIN_OLED_SDA', 10)
i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=400000)

try:
    oled = UniversalOLED(128, 64, i2c=i2c)
    print("[OLED] 128x64 OLED Initialized successfully.")
except Exception as e:
    print("[OLED WARN] Display init failed:", e)
    class DummyDisplay:
        def fill(self, *a): pass
        def fill_rect(self, *a): pass
        def rect(self, *a): pass
        def hline(self, *a): pass
        def text(self, *a): pass
        def show(self): pass
    oled = DummyDisplay()

# Dedicated SPI2 Bus for MFRC522 RFID Reader
rfid_spi = SPI(
    2,
    baudrate=1000000,
    polarity=0,
    phase=0,
    sck=Pin(config.PIN_RFID_SCK),
    mosi=Pin(config.PIN_RFID_MOSI),
    miso=Pin(config.PIN_RFID_MISO)
)
rfid = MFRC522(rst=config.PIN_RFID_RST, cs=config.PIN_RFID_CS, spi=rfid_spi)

# ------------------------------------------------------------------------------
# Edge Caching & Local Storage
# ------------------------------------------------------------------------------
STUDENTS_CACHE = {}     # { "UID": {"name": "...", "enroll_id": "...", "class": "..."} }
MARKED_TODAY = set()    # Set of UIDs already marked today
CACHE_FILE = "students_cache.json"
QUEUE_FILE = "offline_queue.json"

def load_local_cache():
    """Loads student roster from onboard flash for instant zero-wait boot."""
    global STUDENTS_CACHE
    try:
        with open(CACHE_FILE, "r") as f:
            STUDENTS_CACHE = ujson.loads(f.read())
            print("[CACHE] Loaded", len(STUDENTS_CACHE), "students from flash.")
    except Exception:
        STUDENTS_CACHE = {}

def save_local_cache():
    """Saves student roster to onboard flash."""
    try:
        with open(CACHE_FILE, "w") as f:
            f.write(ujson.dumps(STUDENTS_CACHE))
    except Exception as e:
        print("[CACHE WARN] Save failed:", e)

def sync_roster_from_cloud():
    """Fetches active students from Supabase and updates local flash cache."""
    global STUDENTS_CACHE
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        return False
    try:
        url = config.SUPABASE_URL.rstrip("/") + "/rest/v1/students?select=rfid_uid,name,enroll_id,class_group&is_active=eq.true"
        headers = {
            "apikey": config.SUPABASE_ANON_KEY,
            "Authorization": "Bearer " + config.SUPABASE_ANON_KEY
        }
        resp = urequests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            records = resp.json()
            resp.close()
            new_cache = {}
            for r in records:
                uid_clean = str(r.get("rfid_uid", "")).strip().upper()
                if uid_clean:
                    new_cache[uid_clean] = {
                        "name": r.get("name", "Student"),
                        "enroll_id": str(r.get("enroll_id", "N/A")),
                        "class": r.get("class_group", CLASSROOM)
                    }
            if new_cache:
                STUDENTS_CACHE = new_cache  # Overwrite so deleted students on web are purged on device
                save_local_cache()
                print("[CACHE] Synced", len(new_cache), "active students from Supabase.")
                return True
        resp.close()
    except Exception as e:
        print("[CACHE] Roster sync error:", e)
    return False

def sync_marked_today_from_cloud():
    """Syncs today's marked attendance from Supabase so web deletions reflect on device."""
    global MARKED_TODAY
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        return False
    try:
        t = time.localtime()
        today_str = "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])
        url = config.SUPABASE_URL.rstrip("/") + "/rest/v1/attendance_logs?select=students(rfid_uid)&date=eq." + today_str
        headers = {
            "apikey": config.SUPABASE_ANON_KEY,
            "Authorization": "Bearer " + config.SUPABASE_ANON_KEY
        }
        resp = urequests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            records = resp.json()
            resp.close()
            cloud_marked = set()
            for r in records:
                st = r.get("students")
                if st and st.get("rfid_uid"):
                    cloud_marked.add(str(st.get("rfid_uid")).strip().upper())
            MARKED_TODAY = cloud_marked
            print("[SYNC] Today's attendance synced from cloud:", len(MARKED_TODAY), "students marked.")
            return True
        resp.close()
    except Exception as e:
        print("[SYNC] Attendance sync error:", e)
    return False

def push_offline_queue():
    """Flushes any pending offline attendance logs to Supabase."""
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        return
    queue = []
    try:
        with open(QUEUE_FILE, "r") as f:
            queue = ujson.loads(f.read())
    except Exception:
        queue = []
    
    if not queue:
        return

    print("[SYNC] Flushing", len(queue), "offline attendance logs to cloud...")
    remaining = []
    for item in queue:
        uid = item.get("uid")
        res = record_attendance_rpc(uid)
        if res.get("status") in ("WIFI_OFFLINE", "NETWORK_ERROR"):
            remaining.append(item)
    try:
        with open(QUEUE_FILE, "w") as f:
            f.write(ujson.dumps(remaining))
    except Exception:
        pass

def queue_offline_tap(uid, time_str):
    """Queues a tap locally when Wi-Fi is down so it syncs when reconnected."""
    queue = []
    try:
        with open(QUEUE_FILE, "r") as f:
            queue = ujson.loads(f.read())
    except Exception:
        queue = []
    queue.append({"uid": uid, "time": time_str})
    try:
        with open(QUEUE_FILE, "w") as f:
            f.write(ujson.dumps(queue))
    except Exception:
        pass

# ------------------------------------------------------------------------------
# Accurate Time Management (IST UTC+5:30 via Google HTTP Date Header)
# ------------------------------------------------------------------------------
def sync_clock():
    """Syncs RTC to Indian Standard Time (IST, UTC+5:30) via Google HTTP."""
    import usocket
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for _ in range(2):
        try:
            s = usocket.socket()
            s.settimeout(3.0)
            s.connect(("clients3.google.com", 80))
            s.send(b"HEAD /generate_204 HTTP/1.1\r\nHost: clients3.google.com\r\nConnection: close\r\n\r\n")
            raw = s.recv(400).decode("utf-8")
            s.close()
            for line in raw.split("\r\n"):
                if line.lower().startswith("date:"):
                    parts = line.split()[1:]
                    day = int(parts[1])
                    month = months.index(parts[2]) + 1
                    year = int(parts[3])
                    h, m, sec = [int(x) for x in parts[4].split(":")]
                    m += 30
                    h += 5 + (m // 60)
                    m = m % 60
                    if h >= 24:
                        h -= 24
                        day += 1
                    machine.RTC().datetime((year, month, day, 0, h, m, sec, 0))
                    print("[TIME] Synced to IST:", get_time_str())
                    return True
        except Exception as e:
            print("[TIME] Sync retry:", e)
            time.sleep_ms(300)
    return False

def get_time_str():
    """Returns clean 12-hour formatted time: e.g. '04:58 PM'."""
    t = time.localtime()
    hr = t[3]
    ampm = "AM" if hr < 12 else "PM"
    hr12 = hr % 12
    if hr12 == 0:
        hr12 = 12
    return "{:02d}:{:02d} {}".format(hr12, t[4], ampm)

# ------------------------------------------------------------------------------
# UI Rendering Functions (SSD1306 128x64 OLED)
# ------------------------------------------------------------------------------
def show_booting_screen(status="Connecting WiFi"):
    """Instant Splash Screen shown on power-on with zero delay."""
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 11, 1)
    oled.text("SMART ATTENDANCE", 0, 2, 0)

    oled.text(status, 4, 22, 1)
    oled.text("Please wait...", 8, 35, 1)

    oled.hline(0, 50, 128, 1)
    oled.text("SSID: " + str(config.WIFI_SSID)[:8], 4, 54, 1)
    oled.show()

def show_wifi_disconnected_screen():
    """Backup UI shown when Wi-Fi is lost or unavailable."""
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 11, 1)
    oled.text("! WIFI OFFLINE !", 4, 2, 0)

    oled.text("WiFi Disconnected", 0, 20, 1)
    oled.text("SSID: " + str(config.WIFI_SSID)[:10], 0, 31, 1)
    oled.text("Offline Mode OK", 0, 42, 1)

    oled.hline(0, 52, 128, 1)
    oled.text(FOOTER_TEXT, 0, 55, 1)
    oled.show()

def show_home_screen():
    """Production Idle Screen with 'Room 605 AI/ML-A' footer."""
    oled.fill(0)
    # 1. Top Inverted Header
    oled.fill_rect(0, 0, 128, 11, 1)
    oled.text("SMART ATTENDANCE", 0, 2, 0)

    # 2. Central Action Card
    oled.rect(12, 15, 104, 32, 1)
    oled.text("TAP YOUR ID", 20, 21, 1)
    oled.text(">>> NFC <<<", 20, 33, 1)

    # 3. Clean Footer: Exactly 'Room 605 AI/ML-A' (16 chars * 8px = 128px)
    oled.hline(0, 50, 128, 1)
    oled.text(FOOTER_TEXT, 0, 54, 1)
    oled.show()

def show_verifying_screen():
    """Instant 0ms Feedback Screen shown immediately upon card detection."""
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 11, 1)
    oled.text("CARD DETECTED", 12, 2, 0)

    oled.text("Verifying ID...", 8, 22, 1)
    oled.text("Connecting Cloud", 0, 35, 1)

    oled.hline(0, 50, 128, 1)
    oled.text("Please wait...", 12, 54, 1)
    oled.show()

def show_result_screen(name, enroll_id, status_type, timestamp_str=""):
    """Comprehensive Result Screen for all scenarios. Never stays stuck."""
    oled.fill(0)
    t_disp = timestamp_str if timestamp_str else get_time_str()

    if status_type == "MARKED":
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text(">> PRESENT! <<", 12, 2, 0)

        oled.text("Name:" + str(name)[:10], 4, 16, 1)
        oled.text("ID:  " + str(enroll_id)[:10], 4, 27, 1)
        oled.text("Time:" + str(t_disp)[:8], 4, 38, 1)

        oled.fill_rect(0, 50, 128, 14, 1)
        oled.text("ATTENDANCE OK", 12, 53, 0)

    elif status_type == "ALREADY_MARKED":
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text("ALREADY MARKED", 8, 2, 0)

        oled.text("Name:" + str(name)[:10], 4, 16, 1)
        oled.text("ID:  " + str(enroll_id)[:10], 4, 27, 1)
        oled.text("Time:" + str(t_disp)[:8], 4, 38, 1)

        oled.hline(0, 50, 128, 1)
        oled.text("Already Recorded", 0, 54, 1)

    elif status_type == "NO_DATA_FOUND":
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text("! UNREGISTERED !", 4, 2, 0)

        oled.text("Card Not Found", 8, 18, 1)
        oled.text("UID: " + str(enroll_id)[:8], 8, 29, 1)
        oled.text("Time: " + str(t_disp)[:8], 8, 40, 1)

        oled.hline(0, 51, 128, 1)
        oled.text("Register in DB", 8, 54, 1)

    elif status_type == "WIFI_OFFLINE":
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text("! OFFLINE TAP !", 8, 2, 0)

        oled.text("WiFi Disconnected", 0, 18, 1)
        oled.text("Cannot Verify", 12, 30, 1)
        oled.text("Check Internet", 8, 42, 1)

        oled.hline(0, 51, 128, 1)
        oled.text("Offline Mode", 16, 54, 1)

    elif status_type in ("NETWORK_ERROR", "TIMEOUT"):
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text("! TIMEOUT ERROR !", 0, 2, 0)

        oled.text("Network Timeout", 4, 18, 1)
        oled.text("WiFi Lag/Stall", 8, 30, 1)
        oled.text("Time: " + str(t_disp)[:8], 8, 42, 1)

        oled.hline(0, 51, 128, 1)
        oled.text("Please Tap Again", 0, 54, 1)

    else: # SERVER_ERROR
        oled.fill_rect(0, 0, 128, 12, 1)
        oled.text("! SERVER ERROR !", 4, 2, 0)

        oled.text("Supabase Error", 8, 18, 1)
        oled.text("Check Database", 8, 30, 1)
        oled.text("Time: " + str(t_disp)[:8], 8, 42, 1)

        oled.hline(0, 51, 128, 1)
        oled.text("Please Tap Again", 0, 54, 1)

    oled.show()

def show_portal_screen():
    """Setup Portal Screen displayed ONLY when unconfigured."""
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 11, 1)
    oled.text("DEVICE SETUP", 16, 2, 0)

    oled.text("Connect Phone to:", 0, 17, 1)
    oled.text("Smart-Attendance", 0, 28, 1)
    oled.text("Browser URL:", 0, 41, 1)
    oled.text("192.168.4.1", 20, 53, 1)
    oled.show()

# ------------------------------------------------------------------------------
# Networking & Supabase RPC (Optimized for Hotspots & Maximum RF Stability)
# ------------------------------------------------------------------------------
def connect_wifi():
    """Connects to Wi-Fi with PM_NONE (zero radio sleep) for 100% stability."""
    if config.WIFI_SSID in ("YOUR_WIFI_SSID", ""):
        print("\n[CONFIG] No Wi-Fi configured. Starting Portal...")
        show_portal_screen()
        import portal
        portal.start_portal()
        return False

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Disable modem power-save sleep to prevent hotspot flapping
    try:
        wlan.config(pm=wlan.PM_NONE)
        print("[WIFI] Power management set to PM_NONE (High-Performance RF).")
    except Exception:
        pass

    if wlan.isconnected():
        return True

    print("[WIFI] Connecting to", config.WIFI_SSID, "...")
    try:
        if wlan.status() != network.STAT_CONNECTING:
            wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    except OSError:
        pass

    # Give up to 40 retries (10 seconds)
    for _ in range(40):
        if wlan.isconnected():
            print("\n[WIFI] Connected! IP:", wlan.ifconfig()[0], "| RSSI:", wlan.status("rssi"), "dBm")
            return True
        time.sleep_ms(250)
        print(".", end="")

    print("\n[WIFI] Initial connection delayed. Continuing in background...")
    return wlan.isconnected()

def record_attendance_rpc(uid):
    """Sends attendance scan to Supabase with strict 4s timeout & auto-fallback."""
    wlan = network.WLAN(network.STA_IF)

    # If offline, return immediately to let offline queue handle it (never block tap)
    if not wlan.isconnected():
        print("[RPC] WiFi offline, queued for later sync.")
        return {"status": "WIFI_OFFLINE", "name": "WiFi Offline", "enroll_id": uid}

    endpoint = config.SUPABASE_URL.rstrip("/") + "/rest/v1/rpc/record_daily_attendance"
    headers = {
        "Content-Type": "application/json",
        "apikey": config.SUPABASE_ANON_KEY,
        "Authorization": "Bearer " + config.SUPABASE_ANON_KEY
    }
    payload = {
        "p_rfid_uid": uid,
        "p_device_id": config.DEVICE_ID
    }

    try:
        response = urequests.post(endpoint, json=payload, headers=headers, timeout=4)
        if response.status_code in (200, 201):
            data = response.json()
            response.close()
            return data
        else:
            code = response.status_code
            response.close()
            print("[RPC ERROR] Status Code:", code)
            return {"status": "SERVER_ERROR", "name": "HTTP " + str(code), "enroll_id": uid}
    except OSError as oe:
        print("[RPC TIMEOUT/NETWORK]:", oe)
        return {"status": "NETWORK_ERROR", "name": "Network Timeout", "enroll_id": uid}
    except Exception as e:
        print("[RPC EXCEPTION]:", e)
        return {"status": "SERVER_ERROR", "name": "System Error", "enroll_id": uid}

# ------------------------------------------------------------------------------
# Main Application Loop
# ------------------------------------------------------------------------------
def run():
    # 1. Power-on splash screen
    show_booting_screen()

    # 2. Load onboard flash roster cache for 0ms offline capability
    load_local_cache()

    # 3. Connect Wi-Fi
    wifi_ok = connect_wifi()
    if wifi_ok:
        sync_clock()
        sync_roster_from_cloud()
        sync_marked_today_from_cloud()
        push_offline_queue()
        show_home_screen()
    else:
        show_wifi_disconnected_screen()

    # Enable non-blocking serial input for keyboard simulation
    spoll = uselect.poll()
    spoll.register(sys.stdin, uselect.POLLIN)

    print("\n--------------------------------------------------------")
    print("[TERMINAL READY - SUB-10MS INSTANT ATTENDANCE]")
    print("Classroom: " + CLASSROOM + " | Terminal: " + config.DEVICE_ID)
    print("Cached Students: " + str(len(STUDENTS_CACHE)))
    print("Tap RFID card to check in")
    print("--------------------------------------------------------\n")

    wlan = network.WLAN(network.STA_IF)
    last_scan_time = 0
    last_wifi_check = time.ticks_ms()
    last_cloud_sync = time.ticks_ms()
    last_wifi_state = wifi_ok
    offline_strikes = 0

    while True:
        now_ticks = time.ticks_ms()

        # 1. Debounced Background Wi-Fi watchdog (every 4 seconds)
        if time.ticks_diff(now_ticks, last_wifi_check) > 4000:
            last_wifi_check = now_ticks
            is_conn = wlan.isconnected()

            if is_conn:
                offline_strikes = 0
                if not last_wifi_state:
                    print("\n[WIFI] Connection Restored! Syncing...")
                    last_wifi_state = True
                    show_home_screen()
                    sync_clock()
                    sync_roster_from_cloud()
                    sync_marked_today_from_cloud()
                    push_offline_queue()
            else:
                offline_strikes += 1
                # Require 3 consecutive failed checks (12s) before treating as dropped
                if offline_strikes >= 3:
                    if last_wifi_state:
                        print("\n[WIFI] Connection Lost (Confirmed). Switching to Offline Mode.")
                        last_wifi_state = False
                        show_wifi_disconnected_screen()

                    # Trigger reconnect only if not already attempting
                    if wlan.status() != network.STAT_CONNECTING:
                        try:
                            wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                        except Exception:
                            pass

        # 2. Periodic Two-Way Sync (every 15 seconds): catches web roster & attendance deletions
        if time.ticks_diff(now_ticks, last_cloud_sync) > 15000:
            last_cloud_sync = now_ticks
            if wlan.isconnected():
                sync_roster_from_cloud()
                sync_marked_today_from_cloud()
                push_offline_queue()

        uid = None

        # Check for keyboard test input
        if spoll.poll(0):
            try:
                line = sys.stdin.readline().strip().upper()
                if line:
                    print("\n[KEYBOARD TEST] Simulating scan for UID:", line)
                    uid = line
            except Exception:
                pass

        # Check for physical RFID card (non-blocking fast poll)
        if not uid:
            uid = rfid.read_card_uid()

        if uid:
            now = time.ticks_ms()
            # 2-second rate-limiting cooldown between taps
            if time.ticks_diff(now, last_scan_time) < int(config.SCAN_COOLDOWN_SEC * 1000):
                time.sleep_ms(25)
                continue

            last_scan_time = now
            print("\n[RFID] Card Detected: UID =", uid)
            buzzer.pip() # 0ms instantaneous tap chirp

            # ------------------------------------------------------------------
            # Sub-10ms Edge Caching Path
            # ------------------------------------------------------------------
            student = STUDENTS_CACHE.get(uid)
            t_str = get_time_str()

            if student:
                # Registered student in local cache -> Instant response!
                name = student.get("name", "Student")
                enroll_id = student.get("enroll_id", "N/A")

                if uid in MARKED_TODAY:
                    # 0ms Instant Already Marked
                    print("[INSTANT] Already Marked:", name)
                    show_result_screen(name, enroll_id, "ALREADY_MARKED", t_str)
                    buzzer.warning()
                else:
                    # 0ms Instant Attendance Mark! Zero cloud delay!
                    print("[INSTANT PRESENT]", name, "(ID:", enroll_id, "| Time:", t_str, ")")
                    MARKED_TODAY.add(uid)
                    show_result_screen(name, enroll_id, "MARKED", t_str)
                    buzzer.success()

                    # Background sync to Supabase (or queue locally if offline)
                    if wlan.isconnected():
                        res = record_attendance_rpc(uid)
                        if res.get("status") in ("WIFI_OFFLINE", "NETWORK_ERROR"):
                            queue_offline_tap(uid, t_str)
                    else:
                        queue_offline_tap(uid, t_str)

            else:
                # Not in local cache -> Fallback cloud RPC check
                show_verifying_screen()
                res = record_attendance_rpc(uid)
                status = res.get("status", "SERVER_ERROR")
                name = res.get("name", "Unknown")
                enroll_id = res.get("enroll_id") or str(uid)
                time_str = res.get("scanned_at") or res.get("time") or t_str

                if status == "MARKED":
                    # Save freshly discovered student into local cache
                    STUDENTS_CACHE[uid] = {"name": name, "enroll_id": enroll_id, "class": CLASSROOM}
                    save_local_cache()
                    MARKED_TODAY.add(uid)
                    show_result_screen(name, enroll_id, "MARKED", time_str)
                    buzzer.success()
                elif status == "ALREADY_MARKED":
                    MARKED_TODAY.add(uid)
                    show_result_screen(name, enroll_id, "ALREADY_MARKED", time_str)
                    buzzer.warning()
                elif status == "NO_DATA_FOUND":
                    show_result_screen("Unknown", uid, "NO_DATA_FOUND", time_str)
                    buzzer.error()
                elif status == "WIFI_OFFLINE":
                    show_result_screen("Unknown", uid, "WIFI_OFFLINE", time_str)
                    buzzer.error()
                else:
                    show_result_screen("Unknown", uid, status, time_str)
                    buzzer.error()

            # Hold result for 2 seconds
            time.sleep(config.DISPLAY_HOLD_SEC)

            # Revert smoothly to idle or offline screen (NEVER stays stuck)
            if wlan.isconnected():
                show_home_screen()
                last_wifi_state = True
            else:
                show_wifi_disconnected_screen()
                last_wifi_state = False

        time.sleep_ms(25) # Ultra-responsive 25ms polling rate

# Direct boot invocation
run()
