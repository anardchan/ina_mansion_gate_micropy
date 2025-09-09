import espnow  # type: ignore
import network  # type: ignore
import ntptime  # type: ignore
import time
import struct
from machine import Timer, Pin, I2C  # type: ignore
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from config import SSID, SSID_PW, NTP_SERVERS, UTC_OFFSET, GATE_GUARD_MAC

BTN_DEBOUNCE_MS = 500  # debounce window

# --- OLED Setup ---
i2c = I2C(0)  # default SDA=21, SCL=22 on ESP32
oled = SSD1306_I2C(128, 64, i2c)

def show_lines(lines, hold=2, clear=True):
    """Helper to show multiple lines on OLED."""
    if clear:
        oled.fill(0)
    for idx, line in enumerate(lines):
        oled.text(line, 0, idx * 10)
    oled.show()
    time.sleep(hold)

# --- RFID Setup ---
RST_PIN = 25
CS_PIN = 27
rfid = MFRC522(RST_PIN, CS_PIN)

# ---- PUSH BUTTONS (GPIO 35, 34, 39, 36) ----
last_btn_irqs = {35: 0, 34: 0, 39: 0, 36: 0}

def PinId(pin):
    return int(str(pin)[4:6].rstrip(","))

def handle_button_event(pin: Pin):
    """Debounced button press handler."""
    global last_btn_irqs
    now = time.ticks_ms()
    pin_num = PinId(pin)

    if time.ticks_diff(now, last_btn_irqs[pin_num]) < BTN_DEBOUNCE_MS:
        return  # ignore bounce
    last_btn_irqs[pin_num] = now

    if pin.value():  # pressed = HIGH
        btn_map = {35: "Button1", 34: "Button2", 39: "Button3", 36: "Button4"}
        btn_name = btn_map.get(pin_num, f"Unknown({pin})")

        print(f"[ADMIN] 🔘 {btn_name} pressed")
        show_lines([btn_name, "Pressed"])

# Initialize buttons as interrupt-driven
btn1 = Pin(35, Pin.IN)
btn2 = Pin(34, Pin.IN)
btn3 = Pin(39, Pin.IN)
btn4 = Pin(36, Pin.IN)

for btn in [btn1, btn2, btn3, btn4]:
    btn.irq(trigger=Pin.IRQ_RISING, handler=handle_button_event)


# ---- TIME HELPERS ----

def get_local_time_s():
    """Get local time in seconds since epoch adjusted for UTC offset"""
    return time.time() + UTC_OFFSET


def get_local_time(local_time_s: float = None):
    """Return localtime tuple adjusted for UTC offset"""
    if local_time_s is None:
        local_time_s = get_local_time_s()
    return time.localtime(local_time_s)

def do_sync_time_online(ntp_servers: list, timeout: int = 5) -> bool:
    """
    Attempt to sync board time using a list of NTP servers.
    """
    ntptime.timeout = timeout
    for server in ntp_servers:
        try:
            ntptime.host = server
            ntptime.settime()
            print("[ADMIN] ✅ Time synchronized with:", server)
            show_lines(["Time synced", "with NTP"])
            return True
        except Exception as e:
            print("[ADMIN] ❌ Failed with", server, "| Error:", e)
    return False


# ---- MAIN INIT ----
# Connect to Wi-Fi
sta_if = network.WLAN(network.WLAN.IF_STA)  # Station mode
sta_if.active(True)
sta_if.disconnect()
if not sta_if.isconnected():
    print("[ADMIN] Connecting to network...")
    show_lines(["Connecting", "to WiFi...", SSID])
    sta_if.connect(SSID, SSID_PW)
    while not sta_if.isconnected():
        time.sleep(0.1)
print("[ADMIN] ✅ Connected to network:", sta_if.ifconfig()[0])
print("[ADMIN] ✅ Network channel:", sta_if.config("channel"))
show_lines(["WiFi Connected", sta_if.ifconfig()[0], f"Channel: {sta_if.config('channel')}"], hold = 3)

# Sync time from NTP
if not do_sync_time_online(NTP_SERVERS):
    raise Exception("Could not sync time on startup")

print(f"[ADMIN] Current date/time: {get_local_time()}")
show_lines(["Time Synced", str(get_local_time()[0:3]), str(get_local_time()[3:6])], hold=3) 

# Init ESP-NOW
e = espnow.ESPNow()
e.active(True)
e.add_peer(GATE_GUARD_MAC)


def recv_cb(e):
    while True:
        mac, msg = e.irecv(0)
        if mac is None:
            break

        if mac == GATE_GUARD_MAC:
            print("[ADMIN] Message from Gate Guard:", msg)
            if msg[0] == 0x0C:  # time sync request
                print("[ADMIN] Gate Guard requested time sync")
                show_lines(["Gate Guard", "Time Sync Req"])
                response = b"\x0c" + struct.pack("I", get_local_time_s())
                e.send(GATE_GUARD_MAC, response)
                print("[ADMIN] ✅ Sent time:", get_local_time())
                print("[ADMIN] ✅ Sent time (s):", get_local_time_s())
                show_lines(["Time Sent", "to Gate Guard"])
            else:
                print("[ADMIN] ❓ Unknown message:", msg)
                show_lines(["Unknown msg", str(msg)])


e.irq(recv_cb)


# ---- WEEKLY NTP RESYNC ----

def weekly_resync(timer):
    t = get_local_time()
    weekday = t[6]  # 0=Monday .. 6=Sunday
    hour = t[3]
    minute = t[4]

    if weekday == 6 and hour == 3 and minute == 0:  # Sunday 03:00
        print("[ADMIN] 🕒 Weekly time resync triggered")
        show_lines(["Weekly", "NTP Resync"])
        if do_sync_time_online(NTP_SERVERS):
            print("[ADMIN] ✅ Weekly resync success:", get_local_time())
            show_lines(["Resync Success"])
        else:
            print("[ADMIN] ❌ Weekly resync failed")
            show_lines(["Resync Failed"])

# Non-blocking check every minute
timer = Timer(0)
timer.init(period=60000, mode=Timer.PERIODIC, callback=weekly_resync)

# ---- MAIN LOOP ----
# while True:
#     time.sleep(0.1)  # keep loop responsive