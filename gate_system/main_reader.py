import time
import espnow
import network
from machine import I2C
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from config import GATE_GUARD_MAC, BENINCA_HEAD_MAC

# --- Hardware pins ---
RST_PIN = 25
CS_PIN = 27

# ---- ERROR CODES (constants) ----
ERR_SUCCESS = 0x00
ERR_NOT_FOUND = 0x01
ERR_EXPIRED = 0x02
ERR_WRONG_DIRECTION = 0x03
ERR_ALREADY_USED = 0x04
ERR_NOT_IN_PROGRESS = 0x05
ERR_GRACE_EXPIRED = 0x06
ERR_PAYMENT_PROCESSED = 0x07
ERR_UNKNOWN_READER = 0x08

ERROR_DESCRIPTIONS = {
    ERR_SUCCESS: "ERR_SUCCESS",
    ERR_NOT_FOUND: "CARD_NOT_FOUND",
    ERR_EXPIRED: "CARD_EXPIRED",
    ERR_WRONG_DIRECTION: "WRONG_WAY",
    ERR_ALREADY_USED: "ALREADY_USED",
    ERR_NOT_IN_PROGRESS: "NOT_IN_PROGRESS",
    ERR_GRACE_EXPIRED: "GRACE_EXPIRED",
    ERR_PAYMENT_PROCESSED: "PAYMENT_PROCESSED",
    ERR_UNKNOWN_READER: "ERR_UNKNOWN_READER"
}

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
w0.config(channel = 11)
w0.disconnect()

e = espnow.ESPNow()
e.active(True)
e.add_peer(GATE_GUARD_MAC)
e.add_peer(BENINCA_HEAD_MAC)

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

# --- Main loop ---
def main():
    while True:
        show_lines(["Please scan", "your card."], hold=1)

        uid = wait_for_card()
        show_lines(["Card detected:", uid], hold=2)

        # Send request to _gate_guard
        print(f"[READER] Sending access request for UID={uid}")
        e.send(GATE_GUARD_MAC, b"\x10" + uid.encode())
        show_lines(["Checking access..."], hold=1)

        # Wait for reply
        mac, msg = e.irecv(5000)  # 5s timeout
        if not msg:
            print("[READER] ❌ No response from gate_guard")
            show_lines(["No response", "from Gate Guard"], hold=3)
            continue

        if msg[0] == 0x11 and msg[1] == 0x01:
            # Access granted
            print("[READER] ✅ Access granted")
            show_lines(["Access Granted"], hold=3)
            e.send(BENINCA_HEAD_MAC, b"\x01")  # tell Beninca head
        elif msg[0] == 0x11 and msg[1] == 0x00:
            # Access denied
            reason = msg[2] if len(msg) > 2 else 0xFF
            reason_str = ERROR_DESCRIPTIONS.get(reason, f"0x{reason:02X}")
            print(f"[READER] ❌ Access denied, reason=0x{reason:02X}")
            print(f"[READER] ❌ Access denied, reason={reason_str}")
            show_lines(["Access Denied", "Error", f"{reason_str}"], hold=3)
        else:
            print(f"[READER] ❓ Unknown response: {msg}")
            show_lines(["Unknown response"], hold=3)

        # Delay before next scan
        time.sleep(2)

main()
