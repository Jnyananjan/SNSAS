# ==============================================================================
# st7789.py: MicroPython ST7789 240x320 SPI Color Display Driver
# ==============================================================================

import time
import struct
from machine import Pin, SPI

# Common RGB565 Colors (Modern Light & Dark Theme)
COLOR_BLACK       = 0x0000
COLOR_WHITE       = 0xFFFF
COLOR_HEADER_NAVY = 0x08A5  # #0A1128 Dark Midnight Navy
COLOR_BG_LIGHT    = 0xEF7D  # #EBF3FA Soft Powder Blue / White
COLOR_BG_GREEN    = 0xEFBE  # #EBFBF2 Soft Mint Canvas
COLOR_TEXT_MAIN   = 0x08E6  # #0A1931 Deep Navy text
COLOR_TEXT_MUTED  = 0x6B8D  # #6B7280 Muted Gray
COLOR_PRIMARY_BL  = 0x233D  # #2563EB Vibrant Blue
COLOR_ICE_BLUE    = 0xDF7E  # #DCEAFE Soft Ice Blue
COLOR_BLUE_TEXT   = 0x1A15  # #1E40AF Deep Blue
COLOR_SUCCESS     = 0x04B3  # #059669 Emerald Green
COLOR_DARK_GREEN  = 0x0308  # #065F46 Forest Green text
COLOR_WARNING     = 0xFC61  # #F59E0B Warm Amber
COLOR_DANGER      = 0xD924  # #DC2626 Crimson Red
COLOR_BORDER      = 0xCE79  # #CBD5E1 Slate Border
COLOR_CARD_WHITE  = 0xFFFF

class ST7789:
    WIDTH  = 240
    HEIGHT = 320

    # Commands
    SWRESET = 0x01
    SLPOUT  = 0x11
    NORON   = 0x13
    INVOFF  = 0x20
    INVON   = 0x21
    DISPON  = 0x29
    CASET   = 0x2A
    RASET   = 0x2B
    RAMWR   = 0x2C
    MADCTL  = 0x36
    COLMOD  = 0x3A

    def __init__(self, sck=None, mosi=None, cs=10, dc=9, rst=None, bl=None, spi_id=2, baudrate=20000000, spi=None):
        self.cs  = Pin(cs, Pin.OUT) if cs is not None and cs >= 0 else None
        self.dc  = Pin(dc, Pin.OUT)
        self.rst = Pin(rst, Pin.OUT) if rst is not None and rst >= 0 else None
        self.bl  = Pin(bl, Pin.OUT) if bl is not None and bl >= 0 else None

        if self.cs:
            self.cs.value(1)
        self.dc.value(1)
        if self.bl:
            self.bl.value(1)

        if spi is not None:
            self.spi = spi
        else:
            self.spi = SPI(spi_id, baudrate=baudrate, polarity=0, phase=0,
                           sck=Pin(sck), mosi=Pin(mosi))
        self.init()

    def _write_cmd(self, cmd):
        self.dc.value(0)
        if self.cs:
            self.cs.value(0)
        self.spi.write(bytes([cmd]))
        if self.cs:
            self.cs.value(1)

    def _write_data(self, data):
        self.dc.value(1)
        if self.cs:
            self.cs.value(0)
        self.spi.write(data)
        if self.cs:
            self.cs.value(1)

    def init(self):
        if self.rst:
            self.rst.value(0)
            time.sleep_ms(20)
            self.rst.value(1)
            time.sleep_ms(120)

        self._write_cmd(self.SWRESET)
        time.sleep_ms(150)

        self._write_cmd(self.SLPOUT)
        time.sleep_ms(120)

        # 16-bit RGB565 color format
        self._write_cmd(self.COLMOD)
        self._write_data(bytes([0x55]))

        # Memory data access control (Portrait)
        self._write_cmd(self.MADCTL)
        self._write_data(bytes([0x00]))

        # Display Inversion ON (required for standard ST7789 panels)
        self._write_cmd(self.INVON)

        self._write_cmd(self.NORON)
        time.sleep_ms(10)

        self._write_cmd(self.DISPON)
        time.sleep_ms(120)

    def set_window(self, x0, y0, x1, y1):
        self._write_cmd(self.CASET)
        self._write_data(struct.pack(">HH", x0, x1))
        self._write_cmd(self.RASET)
        self._write_data(struct.pack(">HH", y0, y1))
        self._write_cmd(self.RAMWR)

    def fill_rect(self, x, y, w, h, color):
        """Fills a rectangle with RGB565 color."""
        if x >= self.WIDTH or y >= self.HEIGHT:
            return
        x1 = min(x + w - 1, self.WIDTH - 1)
        y1 = min(y + h - 1, self.HEIGHT - 1)
        num_pixels = (x1 - x + 1) * (y1 - y + 1)
        self.set_window(x, y, x1, y1)

        chunk_size = 512
        color_bytes = struct.pack(">H", color)
        chunk = color_bytes * (chunk_size // 2)

        self.dc.value(1)
        self.cs.value(0)
        remaining = num_pixels * 2
        while remaining > 0:
            to_send = min(remaining, len(chunk))
            self.spi.write(chunk[:to_send])
            remaining -= to_send
        self.cs.value(1)

    def fill_screen(self, color):
        self.fill_rect(0, 0, self.WIDTH, self.HEIGHT, color)

    def draw_rect(self, x, y, w, h, color):
        """Draws rectangle border."""
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)

    def fill_circle(self, cx, cy, r, color):
        """Draws filled circle using horizontal scanlines."""
        r2 = r * r
        for dy in range(-r, r + 1):
            dx = int((r2 - dy * dy) ** 0.5)
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def draw_circle(self, cx, cy, r, color):
        """Draws circle outline using midpoint circle algorithm."""
        x = r
        y = 0
        err = 0
        while x >= y:
            self.fill_rect(cx + x, cy + y, 1, 1, color)
            self.fill_rect(cx + y, cy + x, 1, 1, color)
            self.fill_rect(cx - y, cy + x, 1, 1, color)
            self.fill_rect(cx - x, cy + y, 1, 1, color)
            self.fill_rect(cx - x, cy - y, 1, 1, color)
            self.fill_rect(cx - y, cy - x, 1, 1, color)
            self.fill_rect(cx + y, cy - x, 1, 1, color)
            self.fill_rect(cx + x, cy - y, 1, 1, color)
            if err <= 0:
                y += 1
                err += 2 * y + 1
            if err > 0:
                x -= 1
                err -= 2 * x + 1

    def fill_round_rect(self, x, y, w, h, r, color):
        """Draws smooth rounded rectangle."""
        # Central cross
        self.fill_rect(x + r, y, w - 2 * r, h, color)
        self.fill_rect(x, y + r, r, h - 2 * r, color)
        self.fill_rect(x + w - r, y + r, r, h - 2 * r, color)
        # 4 corners
        r2 = r * r
        for dy in range(r):
            dx = int((r2 - (r - dy) ** 2) ** 0.5)
            # Top-left & Top-right
            self.fill_rect(x + r - dx, y + dy, dx, 1, color)
            self.fill_rect(x + w - r, y + dy, dx, 1, color)
            # Bottom-left & Bottom-right
            self.fill_rect(x + r - dx, y + h - 1 - dy, dx, 1, color)
            self.fill_rect(x + w - r, y + h - 1 - dy, dx, 1, color)

    def draw_checkmark(self, cx, cy, color=COLOR_WHITE):
        """Draws crisp checkmark centered at (cx, cy)."""
        # Left stroke down-right, right stroke up-right
        for w in range(3):
            for i in range(7):
                self.fill_rect(cx - 10 + i, cy - 2 + i + w, 1, 1, color)
            for j in range(14):
                self.fill_rect(cx - 3 + j, cy + 5 - j + w, 1, 1, color)

    def draw_text(self, x, y, string, color=COLOR_WHITE, bg=None, size=1):
        """Clean 8x8 bitmap font renderer scalable by integer multiplier."""
        # Standard compact 8x8 font table representation
        import framebuf
        w = len(string) * 8
        h = 8
        buf = bytearray(w * h // 8)
        fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)
        fb.fill(0)
        fb.text(string, 0, 0, 1)

        # Scale and render to display
        if size == 1:
            for py in range(h):
                for px in range(w):
                    if fb.pixel(px, py):
                        self.fill_rect(x + px, y + py, 1, 1, color)
                    elif bg is not None:
                        self.fill_rect(x + px, y + py, 1, 1, bg)
        else:
            for py in range(h):
                for px in range(w):
                    if fb.pixel(px, py):
                        self.fill_rect(x + (px * size), y + (py * size), size, size, color)
                    elif bg is not None:
                        self.fill_rect(x + (px * size), y + (py * size), size, size, bg)

    def draw_centered_text(self, y, string, color=COLOR_WHITE, bg=None, size=1):
        str_w = len(string) * 8 * size
        x = max(0, (self.WIDTH - str_w) // 2)
        self.draw_text(x, y, string, color, bg, size)

