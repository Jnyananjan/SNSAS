# Mass Production & Onboarding Guide

The Smart RFID Attendance Terminal is designed for seamless mass production and field deployment. You can flash the exact same binary image across hundreds of ESP32-S3 devices without hardcoding passwords, endpoints, or room IDs.

---

## 1. How It Works

1. **Flash Once**: The factory flashes the generic firmware binary onto all ESP32-S3 boards.
2. **First Boot (Setup Mode)**: When a fresh device powers on for the first time, it detects no stored credentials in flash memory (NVS) and automatically starts an Access Point:
   - **Wi-Fi SSID**: `Smart-Attendance-Setup`
   - **IP Address**: `192.168.4.1`
3. **Web Onboarding**: The installer or teacher connects their smartphone, tablet, or laptop to the `Smart-Attendance-Setup` Wi-Fi network.
   - A captive portal automatically pops up (or open `http://192.168.4.1`).
   - The user inputs the local Wi-Fi SSID, password, Supabase Project URL, anon key, and Terminal Device ID (e.g. `CLASSROOM_101`).
   - Clicking **Save & Reboot Terminal** commits settings to flash NVS and reboots into normal attendance mode.
4. **Relocation & Factory Reset**: If a terminal is moved to a new classroom or network:
   - Press and hold the onboard **BOOT button (GPIO 0)** for **3 seconds**.
   - The device wipes the stored credentials, displays the setup instructions on the TFT screen, and reopens the Access Point onboarding portal.

---

## 2. Light-Themed Web Portal UI

The web portal is mobile-optimized and uses a clean, light color palette:
- **Background**: `#F8FAFC` (soft slate)
- **Card**: `#FFFFFF` (pure white with subtle shadow)
- **Accent**: `#2563EB` (vibrant blue action button)
- **Fields**:
  - Wi-Fi Network Name (SSID)
  - Wi-Fi Password
  - Supabase Project URL
  - Supabase Anon Key
  - Terminal Device ID

---

## 3. Factory Reset Options

| Method | When to Use | Action |
|:---|:---|:---|
| **Power-On Reset** | Device is powered off | Hold the onboard **BOOT** button down while plugging in USB power. |
| **Runtime Reset** | Device is already running | Hold the onboard **BOOT** button down continuously for **3 seconds**. |
| **Failover Auto-Portal** | Wi-Fi password changed | If the device fails to connect to the saved Wi-Fi after 25 attempts, it automatically falls back to Setup Portal mode. |

