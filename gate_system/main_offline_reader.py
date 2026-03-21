import time
import espnow  # type: ignore
import network  # type: ignore
from machine import I2C  # type: ignore
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from config import (
    BENINCA_HEAD_MAC,
    CHANNEL,
)

# --- Hardware pins ---
RST_PIN = 25
CS_PIN = 27

# --- Init OLED (I2C0 defaults: sda=21, scl=22 on ESP32) ---
i2c = I2C(0)
oled = SSD1306_I2C(128, 64, i2c)


def show_lines(lines, hold=2, clear=True):
    """Helper to show multiple lines on OLED."""
    if clear:
        oled.fill(0)
    for idx, line in enumerate(lines):
        oled.text(line, 0, idx * 10)
    oled.show()
    time.sleep(hold)


# --- Init RFID reader ---
rfid = MFRC522(RST_PIN, CS_PIN)

# --- Init ESP-NOW ---
w0 = network.WLAN(network.STA_IF)
w0.active(True)
w0.config(channel=CHANNEL)
w0.disconnect()

MY_MAC = w0.config("mac")

e = espnow.ESPNow()
e.active(True)
e.add_peer(BENINCA_HEAD_MAC)


# -- Valid cards --
# First line are the admin blue cards
# Second line are the long term cards (1 year)
# Third line are for Sir Thad and Sir Roman
valid_uids = (
    ["0x534AC313C9", "0xA385C413F1", "0x11EBFD0007"]
    + ["0x6BB662B20D", "0x040664B9DF", "0x7B26BBA640", "0xB6312F9C34"]
    + ["0x384C80D723", "0xB647959CF8"]
)


# --- RFID helper ---
def wait_for_card():
    """Block until a card is detected, return UID string."""
    print("[READER] Waiting for card...")
    while True:
        (stat, tag_type) = rfid.request(rfid.REQIDL)
        if stat == rfid.OK:
            (stat, raw_uid) = rfid.anticoll()
            if stat == rfid.OK:
                uid_str = "0x" + "".join("{:02X}".format(i) for i in raw_uid)
                print(f"[READER] Detected card UID={uid_str}")
                return uid_str
        time.sleep(1)


# --- Main loop ---
def main():
    while True:
        show_lines(["Please scan", "your card."])
        show_lines([""])

        uid = wait_for_card()
        show_lines(["Card detected:", uid])

        if uid in valid_uids:
            show_lines(["Attempting to", "open gate."])
            e.send(BENINCA_HEAD_MAC, b"\x01")
        else:
            show_lines(["Card is", "invalid.", "Proceed to the", "guard."])

        print(f"{uid}")

        # Delay before next scan
        time.sleep(2)


main()
