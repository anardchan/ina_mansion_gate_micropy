import espnow  # type: ignore
import time
import struct
from machine import Timer
from config import ADMIN_MAC, GATE_GUARD_MAC, UTC_OFFSET


# ---- GLOBAL STATE ----
local_time_offset = None  # correction offset from board RTC to synced local time


def get_local_time_s():
    """Return local time in seconds since epoch (with UTC offset + correction)."""
    if local_time_offset is None:
        return time.time() + UTC_OFFSET
    return time.time() + UTC_OFFSET + local_time_offset


def get_local_time():
    """Return local time tuple adjusted for offset."""
    return time.localtime(get_local_time_s())


# ---- ESP-NOW ----
e = espnow.ESPNow()
e.active(True)
e.add_peer(ADMIN_MAC)


def request_time_from_admin():
    """Send a time sync request to the admin board."""
    print("[GATE GUARD] ⏳ Requesting time from Admin...")
    e.send(ADMIN_MAC, b"\x0c")


def recv_cb(e):
    global local_time_offset
    while True:
        mac, msg = e.irecv(0)
        if mac is None:
            break

        if mac == ADMIN_MAC and msg[0] == 0x0C:  # Admin's time response
            received_time = struct.unpack("d", msg[1:])[0]
            local_time_offset = received_time - (time.time() + UTC_OFFSET)
            print(f"[GATE GUARD] ✅ Time updated from Admin: {get_local_time()}")
        else:
            print("[GATE GUARD] Unknown message:", msg)


e.irq(recv_cb)


# ---- STARTUP TIME SYNC (BLOCKING) ----
while local_time_offset is None:
    request_time_from_admin()
    time.sleep(2)  # wait before retrying


print("[GATE GUARD] Boot time synchronized:", get_local_time())


# ---- WEEKLY RESYNC ----
def weekly_resync(timer):
    tm = get_local_time()
    # Sunday = 6, 4:00 AM = hour=4, min=0
    if tm[6] == 6 and tm[3] == 4 and tm[4] == 0:
        request_time_from_admin()


weekly_timer = Timer(0)
weekly_timer.init(period=60000, mode=Timer.PERIODIC, callback=weekly_resync)


# ---- MAIN LOOP ----
while True:
    time.sleep(1)
