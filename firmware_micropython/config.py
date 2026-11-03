# ==============================================================================
# config.py: MicroPython Configuration for ESP32-S3 Smart Attendance Terminal
# ==============================================================================

# Wi-Fi Credentials
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Supabase Project Credentials
# Replace with your actual project URL and anon key from Supabase Dashboard
SUPABASE_URL = "https://xyzproject.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
DEVICE_ID = "Room605"

# Hardware Pins (ESP32-S3 DevKit)
# SSD1306 128x64 I2C OLED Display
PIN_OLED_SCL = 9   # CLK / SCL
PIN_OLED_SDA = 10  # MOCI / MOSI / SDA

# ST7789 240x320 SPI TFT (Preserved for future use)
PIN_TFT_SCK  = 12
PIN_TFT_MOSI = 11
PIN_TFT_CS   = 10
PIN_TFT_DC   = 9
PIN_TFT_RST  = 14
PIN_TFT_BL   = 21

# MFRC522 RFID SPI
PIN_RFID_SCK  = 12  # Shared SPI SCK
PIN_RFID_MOSI = 11  # Shared SPI MOSI
PIN_RFID_MISO = 13  # Dedicated SPI MISO
PIN_RFID_CS   = 8   # Dedicated RFID SDA/CS
PIN_RFID_RST  = 18  # Dedicated RFID RST

# Active Buzzer Pin
PIN_BUZZER = 4

# Timing (seconds)
SCAN_COOLDOWN_SEC = 2.0
DISPLAY_HOLD_SEC  = 2.0

