import network
import config
import espnow
import struct
import time

# --- ROLE DEFINITIONS ---
ROLE_MAP = {
    config.RUNNER_A_MAC: "runner_a",
    config.RUNNER_B_MAC: "runner_b",
    config.RUNNER_C_MAC: "runner_c",
    config.RUNNER_D_MAC: "runner_d",
    config.RUNNER_E_MAC: "runner_e",
    config.INSIDE_READER_MAC: "inside_reader",
    config.OUTSIDE_READER_MAC: "outside_reader",
    config.GATE_GUARD_MAC: "gate_guard"
}

ROUTE_ORDER = [
    config.INSIDE_READER_MAC,
    config.OUTSIDE_READER_MAC,
    config.RUNNER_A_MAC,
    config.RUNNER_B_MAC,
    config.RUNNER_C_MAC,
    config.RUNNER_D_MAC,
    config.RUNNER_E_MAC,
    config.GATE_GUARD_MAC
]

# Global state
e = None
MY_MAC = None
MY_ROLE = None


# --- INIT FUNCTIONS ---

def identify_self(mac):
    return ROLE_MAP.get(mac, "unknown")

def get_next_hop(current_mac, direction="upstream"):
    try:
        idx = ROUTE_ORDER.index(current_mac)
        if direction == "upstream":
            return ROUTE_ORDER[idx + 1] if idx + 1 < len(ROUTE_ORDER) else None
        elif direction == "downstream":
            return ROUTE_ORDER[idx - 1] if idx - 1 >= 0 else None
    except ValueError:
        return None

def determine_direction(source_mac, my_mac):
    if source_mac == config.GATE_GUARD_MAC:
        return "downstream"
    elif source_mac in (config.INSIDE_READER_MAC, config.OUTSIDE_READER_MAC):
        return "upstream"
    else:
        try:
            source_index = ROUTE_ORDER.index(source_mac)
            my_index = ROUTE_ORDER.index(my_mac)
            return "upstream" if source_index < my_index else "downstream"
        except ValueError:
            return "unknown"


# --- ISR CALLBACK ---
def recv_cb(e_ref):
    """ESP-NOW interrupt callback for handling received messages."""
    global MY_MAC

    while True:
        mac, msg = e_ref.irecv(0)
        if mac is None:
            break

        print(f"📥 Interrupt received from MAC: {mac}")
        if msg:
            handle_received_data(mac, msg)

# --- DATA HANDLING ---
def handle_received_data(source_mac, data):
    """
    Handle received data and decide routing direction.
    """
    direction = determine_direction(source_mac, MY_MAC)
    next_hop = get_next_hop(MY_MAC, direction)

    print("🧾 Data received:", data)
    print("🧭 Direction:", direction)
    print("➡️ Next hop:", next_hop, " - ", ROLE_MAP[next_hop])

    if next_hop:
        send_data_to(next_hop, data)
    else:
        print("✅ No further forwarding needed. Processing locally.")

def send_data_to(mac, data):
    """
    Send data to a peer via ESP-NOW.
    """
    try:
        e.send(mac, data)
        print(f"📤 Data sent to {mac}: {data}")
    except Exception as ex:
        print(f"❌ Failed to send to {mac}: {ex}")


# === INITIALIZATION ===
# Called when the board boots
w0 = network.WLAN(network.WLAN.IF_STA)
w0.active(True)
w0.config(channel=config.CHANNEL)
w0.disconnect()

MY_MAC = w0.config('mac')
MY_ROLE = identify_self(MY_MAC)

print("🏁 Runner starting...")
print("🔧 My MAC:", MY_MAC)
print("🪪 Role:", MY_ROLE)

# === ESP-NOW SETUP ===
e = espnow.ESPNow()
e.active(True)

# Add known peers manually (or dynamically later)
for peer_mac in ROUTE_ORDER:
    if peer_mac and peer_mac != MY_MAC:
        try:
            e.add_peer(peer_mac)
        except Exception as ex:
            print(f"⚠️ Could not add peer {peer_mac}: {ex}")

# Attach IRQ callback
e.irq(recv_cb)

# Ready to receive and route
print("🚦 Ready to receive ESP-NOW messages.")
