"""
runner_board.py

Intermediate board used to extend ESP-NOW communication range.
Repeats messages between admin_board and other devices.

Author: Allan Bernard Chan
"""

import espnow  # type: ignore
import network  # type: ignore

def add_peer(e_obj: espnow.ESPNow ,mac: bytearray) -> None:
    """
    Adds a peer to the ESP-NOW peer list.

    Args:
        e_obj (espnow.ESPNow): ESP-NOW object to add the peer to.
        mac (bytes): MAC address of the peer.
    """
    try:
        e_obj.add_peer(mac)
    except Exception as ex:
        print(f"[ESPNow] Failed to add peer {mac}. It may already exist. Exception: {ex}")

# Update with real MACs
ADMIN_MAC = b'\x1c\x69\x20\xce\xf8\xe4'
READER_MACS = {
    b'\x84\x0d\x8e\xae\x59\x66',
    b'\x08\xa6\xf7\xbc\xe5\x48',
    b'\xc8\x2e\x18\x51\x7e\xe8',
}  # Inside, outside reader MACs, and test board MAC

# A WLAN interface must be active to send()/recv() via ESP-NOW
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # Ensure no active connections

# Initialize and activate ESP-NOW
e = espnow.ESPNow()
e.active(True)

# Add peers to the ESP-NOW instance
add_peer(e, ADMIN_MAC)  # Add admin peer
for mac in READER_MACS:
    add_peer(e, mac)  # Add reader peers

def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None or msg is None:
            continue
        print(f"[RUNNER] Relay: {mac} -> {msg}")

        if mac in READER_MACS:  # If message from a reader
            print(f"[RUNNER] Forwarding to admin: {msg}")
            e.send(ADMIN_MAC, msg)  # Forward messages from readers to admin

        elif mac == ADMIN_MAC:  # If message from admin
            # Forward messages from admin to all readers
            print(f"[RUNNER] Forwarding to readers: {msg}")
            # Iterate through all reader MACs and send the message
            for reader_mac in READER_MACS:
                e.send(reader_mac, msg)

# Enable the ESP-NOW interrupt service
e.irq(recv_cb)
