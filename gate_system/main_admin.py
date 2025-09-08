import espnow  # type: ignore
import network  # type: ignore
import ntptime  # type: ignore
import time
import struct
from machine import Timer # type: ignore
from config import SSID, SSID_PW, NTP_SERVERS, UTC_OFFSET, GATE_GUARD_MAC


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
            return True
        except Exception as e:
            print("[ADMIN] ❌ Failed with", server, "| Error:", e)
    return False


# ---- MAIN INIT ----

# Connect the board to the Wi-Fi network.
sta_if = network.WLAN(network.WLAN.IF_STA)  # Station mode
sta_if.active(True)
sta_if.disconnect()
if not sta_if.isconnected():
    print("[ADMIN] Connecting to network...")
    sta_if.connect(SSID, SSID_PW)
    while not sta_if.isconnected():
        time.sleep(0.1)
print("[ADMIN] ✅ Connected to network:", sta_if.ifconfig()[0])
print("[ADMIN] ✅ Network channel:", sta_if.config("channel"))

if not do_sync_time_online(NTP_SERVERS):
    raise Exception("Could not sync time on startup")

print(f"[ADMIN] Current date/time: {get_local_time()}")

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
                response = b"\x0c" + struct.pack("I", get_local_time_s())
                e.send(GATE_GUARD_MAC, response)
                print("[ADMIN] Sent time:", get_local_time())
                print("[ADMIN] Sent time (s):", get_local_time_s())
            else:
                print("[ADMIN] Unknown message:", msg)


e.irq(recv_cb)


# ---- WEEKLY NTP RESYNC ----

def weekly_resync(timer):
    t = get_local_time()
    weekday = t[6]  # 0=Monday .. 6=Sunday
    hour = t[3]
    minute = t[4]

    if weekday == 6 and hour == 3 and minute == 0:  # Sunday 03:00
        print("[ADMIN] 🕒 Weekly time resync triggered")
        if do_sync_time_online(NTP_SERVERS):
            print("[ADMIN] ✅ Weekly resync success:", get_local_time())
        else:
            print("[ADMIN] ❌ Weekly resync failed")


# Check once a minute (non-blocking)
timer = Timer(0)
timer.init(period=60000, mode=Timer.PERIODIC, callback=weekly_resync)


# # Keep alive
# while True:
#     time.sleep(1)
