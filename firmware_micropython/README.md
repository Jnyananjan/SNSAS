# MicroPython Firmware Guide (ESP32-S3 Smart Attendance Terminal)

This directory contains the pure-Python production firmware running on the **ESP32-S3 DevKit**.

---

## 📂 Architecture & Files

* **`main.py`**: Core application runtime featuring sub-10ms edge caching, offline sync queue, 4-second cloud RPC timeout, Google HTTP Date clock sync, and debounced Wi-Fi watchdog.
* **`ssd1306.py`**: Universal 128x64 I2C OLED display driver supporting both SSD1306 and SH1106 controller chips via page-by-page addressing at address `0x3C`.
* **`mfrc522.py`**: Hardware-accelerated 1 MHz SPI driver for MFRC522 RFID / NFC readers (ISO/IEC 14443 Type A, 13.56 MHz).
* **`buzzer.py`**: Multi-tone audio driver for active piezo buzzers on GPIO 4 (instant 25ms tap pip, double-chirp success, single warning tone, 3-click error alarm).
* **`portal.py`**: Zero-configuration captive portal Web & DNS server (`192.168.4.1`) launched if no Wi-Fi credentials are set.
* **`config.py`**: Hardware pinouts and template credentials.
* **`students_cache.json`**: Onboard flash storage for the local student roster cache.

---

## ⚡ Flashing Instructions

1. **Install dependencies**:
   ```bash
   pip install esptool mpremote
   ```

2. **Flash standard MicroPython (ESP32-S3)**:
   ```bash
   esptool.py --chip esp32s3 --port COM6 erase_flash
   esptool.py --chip esp32s3 --port COM6 write_flash -z 0 ESP32_GENERIC_S3.bin
   ```

3. **Configure `config.py`**:
   Fill in your Wi-Fi credentials, Supabase project URL, and public anon key in `config.py`.

4. **Upload files to the board**:
   ```bash
   mpremote connect COM6 fs cp config.py :config.py
   mpremote connect COM6 fs cp buzzer.py :buzzer.py
   mpremote connect COM6 fs cp ssd1306.py :ssd1306.py
   mpremote connect COM6 fs cp mfrc522.py :mfrc522.py
   mpremote connect COM6 fs cp portal.py :portal.py
   mpremote connect COM6 fs cp students_cache.json :students_cache.json
   mpremote connect COM6 fs cp main.py :main.py
   ```

5. **Soft Reset & Monitor**:
   ```bash
   mpremote connect COM6 reset
   ```

---

## 💡 Edge Caching & Two-Way Sync Logic

1. **On Boot**:
   * Loads `students_cache.json` from flash immediately for instant offline boot.
   * Connects to Wi-Fi with `wlan.PM_NONE` (modem power-save disabled).
   * Syncs hardware RTC to Indian Standard Time (IST, UTC+5:30) via Google HTTP Date header (`clients3.google.com:80`).
   * Automatically downloads active student roster from Supabase (`GET /rest/v1/students`).
   * Automatically downloads today's active attendance logs from Supabase (`GET /rest/v1/attendance_logs`).
2. **On Tap**:
   * Checks in-memory cache in **`< 5ms`**.
   * If student is found and not yet marked today:
     * Displays `>> PRESENT! <<` and chirps buzzer immediately.
     * Marks student present locally and sends background RPC to Supabase.
     * If Wi-Fi is offline, queues the tap in `offline_queue.json`.
   * If student was already marked today:
     * Instantly displays `ALREADY MARKED` and sounds warning tone.
   * If card is unknown:
     * Displays `! UNREGISTERED !` and sounds 3 error clicks.
3. **Web Deletions**:
   * If an administrator deletes an attendance record in the Supabase or Google Sheets dashboard, the terminal's 15-second background sync automatically purges the student from `MARKED_TODAY`, allowing them to scan again without rebooting the terminal.
