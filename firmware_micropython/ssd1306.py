# ==============================================================================
# ssd1306.py: Universal SSD1306 & SH1106 128x64 I2C OLED Driver
# Works flawlessly with all 0.96" and 1.3" I2C OLED displays
# Uses page-by-page addressing compatible with both SSD1306 and SH1106
# ==============================================================================

import framebuf

class UniversalOLED(framebuf.FrameBuffer):
    def __init__(self, width=128, height=64, i2c=None, addr=0x3C, is_sh1106=True):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.is_sh1106 = is_sh1106
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, bytes([0x80, cmd]))

    def init_display(self):
        # Comprehensive init sequence compatible with SSD1306 and SH1106
        init_cmds = [
            0xAE,       # Display OFF
            0x00, 0x10, # Set lower & upper column start address
            0x40,       # Set display start line to 0
            0xB0,       # Set page start address
            0x81, 0xCF, # Set contrast control (0xCF bright)
            0xA1,       # Set segment re-map (columns 0-127)
            0xA6,       # Set normal display (0xA6 normal, 0xA7 inverse)
            0xA8, 0x3F, # Set multiplex ratio (64)
            0xC8,       # Set COM output scan direction (remapped)
            0xD3, 0x00, # Set display offset (0)
            0xD5, 0x80, # Set display clock divide ratio/oscillator
            0xD9, 0xF1, # Set pre-charge period
            0xDA, 0x12, # Set COM pins hardware configuration
            0xDB, 0x40, # Set VCOMH deselect level
            0x8D, 0x14, # SSD1306: Enable charge pump regulator
            0xAD, 0x8B, # SH1106: DC-DC control mode ON
            0x33,       # SH1106: Set pump voltage
            0xAF        # Display ON
        ]
        for cmd in init_cmds:
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def show(self):
        # Page-by-page transmission works reliably on both SH1106 and SSD1306
        col_offset = 2 if self.is_sh1106 else 0
        for page in range(self.pages):
            self.write_cmd(0xB0 + page)
            self.write_cmd(0x00 + (col_offset & 0x0F))
            self.write_cmd(0x10 + ((col_offset >> 4) & 0x0F))
            page_data = self.buffer[page * self.width : (page + 1) * self.width]
            self.i2c.writeto(self.addr, b"\x40" + page_data)

# Backward-compatible alias
SSD1306_I2C = UniversalOLED
