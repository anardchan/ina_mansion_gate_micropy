"""
inside_reader.py

Board located inside the gate. Sends card scans to admin_board
to check if card is valid for exit. Displays status.

Author: Allan Bernard Chan
"""

from machine import I2C
import time
from rfid_reader import RFIDReader
from display_manager import DisplayManager
from espnow_handler import ESPNowHandler

RUNNER_MAC = b'\x1c\x69\x20\xce\xfa\x24'
GATE_CONTROLLER_MAC = b'\xc8\x2e\x18\x51\xc8\x5c'

# Pins
CS = 27
RST = 25
i2c = I2C(0)

rfid = RFIDReader(cs_pin=CS, rst_pin=RST)
oled = DisplayManager(i2c)
esp = ESPNowHandler()
esp.add_peer(RUNNER_MAC)
esp.add_peer(GATE_CONTROLLER_MAC)

def main():
    while True:
        oled.show_lines(["Please scan", "your card."])
        card_id = rfid.wait_for_card()
        oled.show_lines(["Scanned:", card_id, "Checking..."])
        time.sleep(2)  # Allow time for display update

        # Send ID prefixed with 0xA0
        raw_bytes = bytes.fromhex(card_id[2:])
        esp.send(RUNNER_MAC, b'\xa1' + raw_bytes)
        mac, response = esp.recv()
        print(f"[INSIDE READER] Received from {mac}: {response}")
    
        if response == b'\xa2': 
            oled.show_lines(["Access granted"])
            esp.send(GATE_CONTROLLER_MAC, b'\x01')
        elif response == b'\xa2':
            oled.show_lines(["Access denied"])
        elif mac is None and response is None:
            oled.show_lines(["No response from", "Admin Board.", "Try again."])
        else:
            oled.show_lines(["Unexpected response", "from Admin Board."])
        time.sleep(2)  # Allow time for display update

main()
