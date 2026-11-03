#!/usr/bin/env python3
"""
==============================================================================
flash_terminal.py: Automated 1-Click ESP32-S3 MicroPython Installer & Flasher
==============================================================================
No manual tool installation required! This script:
1. Auto-checks and installs Python prerequisites (esptool, mpremote, pyserial).
2. Auto-detects your connected ESP32-S3 COM port (waits if unplugged).
3. Auto-downloads the official ESP32-S3 MicroPython firmware from micropython.org.
4. Erases and flashes the firmware to the ESP32-S3.
5. Uploads all terminal code (config.py, st7789.py, mfrc522.py, buzzer.py, main.py).
6. Soft-resets the board into live attendance mode!
==============================================================================
"""

import os
import sys
import time
import subprocess
import urllib.request

# Official MicroPython ESP32-S3 Generic Binary
MICROPYTHON_URL = "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20240222-v1.22.2.bin"
FALLBACK_URL   = "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20231005-v1.21.0.bin"

BIN_DIR = os.path.join(os.path.dirname(__file__), "firmware_micropython", "bin")
BIN_FILE = os.path.join(BIN_DIR, "ESP32_GENERIC_S3.bin")
SRC_DIR = os.path.join(os.path.dirname(__file__), "firmware_micropython")


# Set UTF-8 encoding for standard output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def step(num, msg):
    print(f"\n[STEP {num}] {msg}")


def info(msg):
    print(f"  [OK] {msg}")


def warn(msg):
    print(f"  [!] {msg}")


def error(msg):
    print(f"  [ERROR] {msg}")


# ------------------------------------------------------------------------------
# 1. Dependency Auto-Installer
# ------------------------------------------------------------------------------
def ensure_dependencies():
    step(1, "Checking Python prerequisites...")
    required = ["serial", "esptool", "mpremote"]
    missing = []

    for mod in required:
        try:
            __import__(mod)
            info(f"Package '{mod}' is ready.")
        except ImportError:
            missing.append(mod if mod != "serial" else "pyserial")

    if missing:
        warn(f"Installing missing tools: {', '.join(missing)}...")
        cmd = [sys.executable, "-m", "pip", "install", *missing]
        subprocess.check_call(cmd)
        info("All prerequisites installed successfully.")


# ------------------------------------------------------------------------------
# 2. ESP32-S3 COM Port Detection
# ------------------------------------------------------------------------------
def find_esp32_port():
    step(2, "Detecting connected ESP32-S3 board...")
    import serial.tools.list_ports as lp

    while True:
        ports = list(lp.comports())
        candidates = []
        for p in ports:
            desc = p.description.lower()
            # Common USB bridge chips used on ESP32-S3 boards
            if any(k in desc for k in ["cp210", "ch340", "ch341", "usb serial", "jtag", "esp32", "uart"]):
                candidates.append(p.device)
            elif "com" in p.device.lower():
                candidates.append(p.device)

        if candidates:
            port = candidates[0]
            info(f"Detected ESP32-S3 on port: \033[1;32m{port}\033[0m")
            return port

        print("  \033[33m[⏳]\033[0m Please plug your ESP32-S3 board into USB... (waiting)", end="\r")
        time.sleep(1.0)


# ------------------------------------------------------------------------------
# 3. MicroPython Binary Auto-Downloader
# ------------------------------------------------------------------------------
def download_micropython_bin():
    step(3, "Checking MicroPython firmware image...")
    os.makedirs(BIN_DIR, exist_ok=True)

    if os.path.exists(BIN_FILE) and os.path.getsize(BIN_FILE) > 1000000:
        info(f"Using cached firmware: {BIN_FILE}")
        return BIN_FILE

    print("  Downloading official MicroPython firmware from micropython.org...")
    for url in [MICROPYTHON_URL, FALLBACK_URL]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(BIN_FILE, "wb") as f:
                f.write(resp.read())
            info(f"Downloaded firmware: {os.path.basename(BIN_FILE)} ({os.path.getsize(BIN_FILE) // 1024} KB)")
            return BIN_FILE
        except Exception as e:
            warn(f"Download mirror failed: {e}. Trying fallback...")

    raise RuntimeError("Could not download MicroPython firmware. Please check internet connection.")


# ------------------------------------------------------------------------------
# 4. Flashing Firmware to ESP32-S3
# ------------------------------------------------------------------------------
def flash_firmware(port, bin_path):
    step(4, f"Flashing MicroPython to ESP32-S3 on {port}...")

    # Erase flash
    print("  Erasing flash memory...")
    erase_cmd = [sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", port, "erase_flash"]
    subprocess.check_call(erase_cmd)
    info("Flash memory erased.")

    # Write firmware at 0x0
    print("  Writing MicroPython firmware image...")
    flash_cmd = [
        sys.executable, "-m", "esptool",
        "--chip", "esp32s3",
        "--port", port,
        "--baud", "921600",
        "write_flash", "-z", "0", bin_path
    ]
    subprocess.check_call(flash_cmd)
    info("MicroPython successfully written to ESP32-S3 flash!")

    print("  Waiting 3 seconds for MicroPython to boot...")
    time.sleep(3.0)


# ------------------------------------------------------------------------------
# 5. Copy Files to ESP32-S3 via mpremote
# ------------------------------------------------------------------------------
def upload_project_files(port):
    step(5, f"Uploading terminal software files to {port}...")
    files = ["config.py", "ssd1306.py", "st7789.py", "mfrc522.py", "buzzer.py", "portal.py", "main.py"]

    for fname in files:
        fpath = os.path.join(SRC_DIR, fname)
        if not os.path.exists(fpath):
            error(f"Missing file: {fpath}")
            continue

        print(f"  Uploading {fname}...")
        cmd = [sys.executable, "-m", "mpremote", "connect", port, "fs", "cp", fpath, f":{fname}"]
        subprocess.check_call(cmd)
        info(f"{fname} uploaded.")

    # Soft-reset board to run main.py
    step(6, "Starting Attendance Terminal...")
    try:
        reset_cmd = [sys.executable, "-m", "mpremote", "connect", port, "reset"]
        subprocess.run(reset_cmd, timeout=3)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("\033[1;32m  🎉 SETUP COMPLETE! YOUR TERMINAL IS RUNNING! 🎉\033[0m")
    print("=" * 60)
    print("The screen is now showing the 'TAP YOUR ID CARD' display.")
    print("Tap your RFID card on the reader to test instant attendance!")
    
    pres_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "presentation.html"))
    if os.path.exists(pres_file):
        print(f"Presentation Deck: file://{pres_file}")
        try:
            import webbrowser
            webbrowser.open(f"file://{pres_file}")
        except Exception:
            pass
    print("=" * 60 + "\n")


# ------------------------------------------------------------------------------
# Main Orchestrator
# ------------------------------------------------------------------------------
def main():
    print("\n========================================================")
    print("  Smart RFID Attendance Terminal: 1-Click Installer")
    print("========================================================")

    try:
        ensure_dependencies()
        port = find_esp32_port()
        bin_path = download_micropython_bin()
        flash_firmware(port, bin_path)
        upload_project_files(port)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        error(f"Installation encountered an error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
