"""
SSD1306 OLED display manager.
"""

from ssd1306 import SSD1306_I2C
import time

class DisplayManager:
    def __init__(self, i2c, width=128, height=64):
        self.oled = SSD1306_I2C(width, height, i2c)

    def show_message(self, message, duration=2):
        self.oled.fill(0)
        self.oled.text(message, 0, 0)
        self.oled.show()
        time.sleep(duration)

    def show_lines(self, lines, clear=True):
        if clear:
            self.oled.fill(0)
        for idx, line in enumerate(lines):
            self.oled.text(line, 0, idx * 10)
        self.oled.show()
