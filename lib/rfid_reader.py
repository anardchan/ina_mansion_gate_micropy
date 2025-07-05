"""
RFID Reader abstraction using MFRC522 on SPI.
"""

from mfrc522 import MFRC522

class RFIDReader:
    def __init__(self, cs_pin, rst_pin):
        self.rdr = MFRC522(rst_pin, cs_pin)

    def wait_for_card(self):
        print("Waiting for card...")
        while True:
            (stat, tag_type) = self.rdr.request(self.rdr.REQIDL)
            if stat == self.rdr.OK:
                (stat, raw_uid) = self.rdr.anticoll()
                if stat == self.rdr.OK:
                    return self._format_uid(raw_uid)

    def _format_uid(self, raw_uid):
        return "0x" + "".join("{:02X}".format(i) for i in raw_uid)
