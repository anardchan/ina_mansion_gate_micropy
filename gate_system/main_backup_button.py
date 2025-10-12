import network  # type: ignore
import espnow  # type: ignore

from config import BENINCA_HEAD_MAC, CHANNEL
from pb_debounce import PinDebounce 

VERBOSE = True
verbose_print = print if VERBOSE else lambda *a, **k: None

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.STA_IF)  # Or network.AP_IF
sta.active(True)
sta.config(channel = CHANNEL)
sta.disconnect() 

e = espnow.ESPNow()
e.active(True)
peer = BENINCA_HEAD_MAC  
e.add_peer(peer)  # Must add_peer() before send()


def pb_cb():
    verbose_print("Button pressed")
    e.send(peer, b"\x01")


debounced_switch = PinDebounce(pin_number=36, callback=pb_cb, debounce_time=500)
debounced_switch.enable_irq()  # Enable IRQ for the switch

mac = sta.config("mac")
print(f"MAC Address: {':'.join("%02x" % b for b in mac)}")