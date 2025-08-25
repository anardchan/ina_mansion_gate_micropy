import espnow  # type: ignore
import ntptime  # type: ignore
import time
import struct
from config import SSID, SSID_PW, NTP_SERVERS, UTC_OFFSET, GATE_GUARD_MAC


def get_local_time_s():
    return (
        time.time() + UTC_OFFSET
    )  # Get local time in seconds since epoch adjusted for UTC offset


def get_local_time(loacl_time_s: float = get_local_time_s()):
    return time.localtime(loacl_time_s)


def do_connect_to_wifi():
    """
    Connect the board to the Wi-Fi network.
    """
    import network  # type: ignore

    sta_if = network.WLAN(network.WLAN.IF_STA)  # Station Mode - board is a client
    sta_if.disconnect()  # Ensure no active connections
    if not sta_if.isconnected():
        print("[ADMIN] Connecting to network...")
        print(f"[ADMIN] SSID: {SSID}")
        sta_if.active(True)
        sta_if.connect(SSID, SSID_PW)
        while not sta_if.isconnected():
            pass
    print("[ADMIN] Connection successful")
    print("[ADMIN] IP Address: {sta_if.ifconfig()[0]}")


def do_sync_time_online(ntp_servers: list, timeout: int = 5) -> bool:
    """
    Attempt to sync board time using a list of NTP servers.

    Args:
        NTP_SERVERS (list): List of NTP server addresses.
        timeout (int): Timeout in seconds for each NTP request.

    Returns:
        bool: True if time sync succeeded, False if all servers failed.
    """
    ntptime.timeout = timeout
    for server in NTP_SERVERS:
        try:
            ntptime.host = server
            ntptime.settime()
            print("[ADMIN] Time synchronized successfully with:", server)
            return True
        except Exception as e:
            print("[ADMIN] Failed to sync with", server, "| Error:", e)

    print("[ADMIN] ❌ All NTP servers failed. Time not synchronized.")
    return False


# Main code

# Connect to wifi
do_connect_to_wifi()

# Sync board time
if not do_sync_time_online(NTP_SERVERS):
    raise Exception("Could not sync time")

# Debug message for getting the current date and time
print(f"Current date and time is: {get_local_time()}")

# Initialize and activate ESP-NOW
e = espnow.ESPNow()
e.active(True)
e.add_peer(GATE_GUARD_MAC)  # Add gate_guard as a peer to be able to send to that device


def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:  # mac, msg will equal (None, None) on timeout
            print("No messages left.")  # Debug message no messages left
            break  # Break out off the while loop

        if mac == GATE_GUARD_MAC:
            print("[ADMIN] Receive message from Gate Guard.")
            if msg[0] == b"\x0c":
                print("[ADMIN] Gate Guard has reqeusted a time sync.")
                print("[ADMIN] Getting local time in s...")
                print(
                    f"[ADMIN] Local time in s = {get_local_time_s()} = {get_local_time}"
                )
                print("[ADMIN] Sending local time...")
                response = b"\x0c"  # response[0]
                response += struct.pack("d", get_local_time_s())  # response[1:9]
                print(f"[ADMIN] Sending packed message: {response}")
                e.send(GATE_GUARD_MAC, response)
                print("[ADMIN] Response sent.")
            else:
                print(f"[ADMIN] Unknown message from Gate Guard: {msg}")


e.irq(recv_cb)  # Enable interrupt callback when an ESP-Now message is received
