# ==============================================================================
# buzzer.py: Hardware Buzzer Driver for Audio Confirmation
# Supports Active Piezo Buzzer (3.3V / 5V) on GPIO 4
# ==============================================================================

import time
from machine import Pin

class Buzzer:
    def __init__(self, pin_num=4):
        self.pin = Pin(pin_num, Pin.OUT)
        self.pin.value(0)

    def pip(self):
        """Ultra-short 25ms pip for instantaneous card tap recognition."""
        self.pin.value(1)
        time.sleep_ms(25)
        self.pin.value(0)

    def success(self):
        """Crisp double-chirp confirming successful attendance mark."""
        self.pin.value(1)
        time.sleep_ms(70)
        self.pin.value(0)
        time.sleep_ms(60)
        self.pin.value(1)
        time.sleep_ms(110)
        self.pin.value(0)

    def warning(self):
        """Single 240ms tone indicating student already marked today."""
        self.pin.value(1)
        time.sleep_ms(240)
        self.pin.value(0)

    def error(self):
        """3 rapid warning clicks indicating unknown card or server error."""
        for _ in range(3):
            self.pin.value(1)
            time.sleep_ms(50)
            self.pin.value(0)
            time.sleep_ms(50)

