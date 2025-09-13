import espnow  # type: ignore
import network  # type: ignore
import ntptime  # type: ignore
import time
import struct
import json
from machine import Timer, Pin, I2C  # type: ignore
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from config import (
    SSID,
    SSID_PW,
    NTP_SERVERS,
    UTC_OFFSET,
    GATE_GUARD_MAC,
    MONTHLY_RATE_PHP,
    DAILY_RATE_PHP,
    GRACE_MINS,
)

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

# --- global mailbox for async messages ---
pending_msgs = []

# ---- PUSH BUTTONS (GPIO 35, 34, 39, 36) ----
BUTTON_PINS = {35: 1, 34: 2, 39: 3, 36: 4}

last_button_irq = {
    i: 0 for i in BUTTON_PINS.keys()
}  # debounce trackers (stores time) {35: 0, 34: 0, 39: 0, 36: 0}
last_button_pressed = (
    None  # stores last GPIO number pressed, not the pin ID , example 35/ 34/ 39/ 36
)


def PinId(pin):
    """Extract integer GPIO number from Pin object."""
    return int(str(pin)[4:6].rstrip(","))


def button_cb(pin):
    """IRQ callback — debounce and mark which button pressed."""
    global last_button_pressed
    now = time.ticks_ms()
    pin_num = PinId(pin)

    if time.ticks_diff(now, last_button_irq[pin_num]) < BTN_DEBOUNCE_MS:
        return  # ignore bounce
    last_button_irq[pin_num] = now

    if pin.value():  # HIGH = pressed
        last_button_pressed = pin_num
        print(f"[ADMIN] 🔘 Button GPIO {pin_num}, ID {BUTTON_PINS[pin_num]} pressed")


# Initialize Pin objects with IRQs
for gpio, b_id in BUTTON_PINS.items():
    btn = Pin(gpio, Pin.IN)
    btn.irq(trigger=Pin.IRQ_RISING, handler=button_cb)

# --- Register flow ---


def wrap_text(text, width=16):
    """
    Word-wrap text into lines of max `width` chars.
    Splits on spaces so words are not cut awkwardly.
    Returns a list of strings.
    """
    words = text.split(" ")
    lines, current = [], ""

    for word in words:
        if len(current) + len(word) + (1 if current else 0) <= width:
            current += (" " if current else "") + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    return lines


def prompt_user(title="", options=None, timeout=None):
    """
    Display a prompt with dynamic options (1-4), with automatic word wrapping.
    Blocks until a valid button is pressed, or timeout expires.

    Args:
        title (str): Optional message/question at the top.
        options (list[str]): List of up to 4 option strings.
                             Each option maps to Button1-Button4.
        timeout (int): Optional timeout in ms. None = no timeout.

    Returns:
        int|None: Button number pressed (1-4), or None if timeout.
    """
    global last_button_pressed
    if options is None:
        options = []

    # --- Render UI ---
    oled.fill(0)
    line = 0

    # Wrap and print title
    if title:
        for wrapped in wrap_text(title):
            oled.text(wrapped, 0, line)
            line += 10

    # Wrap and print each option
    for idx, opt in enumerate(options):
        prefix = f"[B{idx + 1}] "
        wrapped_lines = wrap_text(prefix + opt)
        for w in wrapped_lines:
            oled.text(w, 0, line)
            line += 10

    oled.show()

    # --- Wait for input ---
    start = time.ticks_ms()
    while True:
        if last_button_pressed:
            pressed = last_button_pressed
            last_button_pressed = None
            print(f"[ADMIN] promt_user function returns: {BUTTON_PINS[pressed]}")
            return BUTTON_PINS[pressed]  # Returns the GPIO pin id (1, 2, 3, 4)

        if timeout and time.ticks_diff(time.ticks_ms(), start) > timeout:
            print("[ADMIN] promt_user function returns None. Timed out")
            return None
        time.sleep(0.05)  # 50ms


# CREATE
def register_flow():
    show_lines(["Tap card to", "register..."])
    uid = wait_for_card()  # blocking read from MFRC522
    if not uid:
        print("[ADMIN] Did not find any UID.")
        user_response = None
        user_response = prompt_user("No card detected. Try again?", ["Yes", "No"])
        if user_response == 1:
            print("[ADMIN] Trying to register card again...")
            register_flow()
            return
        elif user_response == 2:
            print("[ADMIN] Register card process cancelled.")
            show_home()
            return
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
            show_home()
            return

    # Step1: check if UID exists
    try:
        print("[ADMIN] Asking gate guard if UID exists in database...")
        e.send(GATE_GUARD_MAC, b"\x20" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return

    # Wait for reply
    start = time.ticks_ms()
    exists = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x21:  # response to UID check
                exists = msg[1] == 0x01
                break
        time.sleep(0.05)
    if exists is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if exists:
        print("[ADMIN] Card already registered.")
        show_lines(["UID already", "registered"], hold=3)
        show_home()
        return

    # Step 2: Choose card type
    user_response = None
    card_registration_error = None
    user_response = prompt_user(
        "Card type?", ["Monthly", "Daily", "Single Entry", "Cancel"]
    )
    if user_response == 1:
        print("[ADMIN] Monthly registration selected")
        show_lines(["Selected:", "Monthly"])
        card_registration_error = handle_card_monthly_registration(uid)
    elif user_response == 2:
        print("[ADMIN] Daily registration selected")
        show_lines(["Selected:", "Daily"])
        card_registration_error = handle_card_daily_registration(uid)
    elif user_response == 3:
        print("[ADMIN] Single-entry registration selected")
        show_lines(["Selected:", "Single entry"])
        card_registration_error = handle_card_se_registration(uid)
    else:
        show_lines(["Cancelled. Returning home"])
        show_home()
        return

    if card_registration_error == 0:
        show_lines(["Registration", "successful."], hold=3)
    elif card_registration_error == 1:
        show_lines(["Send failed", "Retry later"], hold=3)
    elif card_registration_error == 2:
        show_lines(["Could not", "register"], hold=3)
        show_lines(["Try again."], hold=3)
    elif card_registration_error == 3:
        show_lines(["No response", "from database."], hold=3)
        show_lines(["Try again."], hold=3)
    elif card_registration_error == 4:
        show_lines(["Registration", "failed."], hold=3)
        show_lines(["Try again."], hold=3)
    elif card_registration_error == 5:
        show_lines(["Registration", "cancelled."], hold=3)

    show_home()
    return


def handle_card_monthly_registration(uid):
    prompt_user(f"Please pay: Php {MONTHLY_RATE_PHP} for the monthly rate.", ["Ok"])
    user_response = prompt_user("Have you already paid?", ["Yes", "No"])
    if user_response == 1:
        print("[ADMIN] Paid monthly.")
        show_lines(["Paid.", "Please wait..."])
    elif user_response == 2:
        print("[ADMIN] Not paid.")
        show_lines(["Not paid.", "Cancelling..."])
        return 5
    else:
        print("[ADMIN] Wrong button pressed")
        show_lines(["Unknown command.", "Try again."], hold=3)
        return 5

    # Step 2: Build Card Info
    print("[ADMIN] Building monthly card details to register in the database")
    now = get_local_time_s()
    activation = format_time(now)
    expiration = format_time(now + 30 * 24 * 3600)
    card_data = {
        "uid": uid,
        "activation_time": activation,
        "expiration_time": expiration,
        "io_status": "out",
        "status": "new",
    }

    # Step 3: Send to gate_guard
    try:
        payload = json.dumps(card_data)
        if len(payload) > 240:
            return 2  # Data too long error
        e.send(GATE_GUARD_MAC, b"\x22" + payload.encode())
    except Exception:
        return 1  # Send fail error

    # Wait for reply
    start = time.ticks_ms()
    registerd_status = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x23:  # response to UID check
                registerd_status = msg[1] == 0x01
                break
        time.sleep(0.05)
    if registerd_status is None:
        print("[ADMIN] No response from gate guard.")
        return 3  # No response from gate guard
    if registerd_status:
        print("[ADMIN] Card not registered.")
        return 4  # Card not registered
    else:
        pass  # continue

    return 0


def handle_card_daily_registration(uid):
    prompt_user(f"Please pay: Php {DAILY_RATE_PHP} for the daily rate.", ["Ok"])
    user_response = prompt_user("Have you already paid?", ["Yes", "No"])
    if user_response == 1:
        print("[ADMIN] Paid monthly.")
        show_lines(["Paid.", "Please wait..."])
    elif user_response == 2:
        print("[ADMIN] Not paid.")
        show_lines(["Not paid.", "Cancelling..."])
        return 5
    else:
        print("[ADMIN] Wrong button pressed")
        show_lines(["Unknown command.", "Try again."], hold=3)
        return 5

    # Step 2: Build Card Info
    print("[ADMIN] Building daily card details to register in the database")
    now = get_local_time_s()
    activation = format_time(now)
    expiration = format_time(now + 24 * 3600)
    card_data = {
        "uid": uid,
        "activation_time": activation,
        "expiration_time": expiration,
        "io_status": "out",
        "status": "new",
    }

    # Step 3: Send to gate_guard
    try:
        payload = json.dumps(card_data)
        if len(payload) > 240:
            return 2  # Data too long error
        e.send(GATE_GUARD_MAC, b"\x52" + payload.encode())
    except Exception:
        return 1  # Send fail error

    # Wait for reply
    start = time.ticks_ms()
    registerd_status = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x62:  # response to UID check
                registerd_status = msg[1] == 0x01
                break
        time.sleep(0.05)
    if registerd_status is None:
        print("[ADMIN] No response from gate guard.")
        return 3  # No response from gate guard
    if registerd_status:
        print("[ADMIN] Card not registered.")
        return 4
    else:
        pass  # continue

    return 0


def handle_card_se_registration(uid):
    print("[ADMIN] Single entry card registration.")
    show_lines(["Please wait..."])

    # Step 2: Build Card Info
    print("[ADMIN] Building single entry card details to register in the database")
    now = get_local_time_s()
    activation = format_time(now)
    card_data = {
        "uid": uid,
        "entry_time": activation,
        "io_status": "out",
        "status": "new",
    }

    # Step 3: Send to gate_guard
    try:
        payload = json.dumps(card_data)
        if len(payload) > 240:
            return 2  # Data too long error
        e.send(GATE_GUARD_MAC, b"\x53" + payload.encode())
    except Exception:
        return 1  # Send fail error

    # Wait for reply
    start = time.ticks_ms()
    registerd_status = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x63:  # response to single entry registration
                registerd_status = msg[1] == 0x01
                break
        time.sleep(0.05)
    if registerd_status is None:
        print("[ADMIN] No response from gate guard.")
        return 3  # No response from gate guard
    if registerd_status:
        print("[ADMIN] Card not registered.")
        return 4  # Card not registered
    else:
        pass  # continue

    return 0

# READ
def read_flow():
    show_lines(["Tap card to", "read..."])
    uid = wait_for_card()  # blocking read from MFRC522
    if not uid:
        print("[ADMIN] Did not find any UID.")
        user_response = None
        user_response = prompt_user("No card detected. Try again?", ["Yes", "No"])
        if user_response == 1:
            print("[ADMIN] Trying to read card again...")
            read_flow()
            return
        elif user_response == 2:
            print("[ADMIN] Reading card process cancelled.")
            show_home()
            return
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
            show_home()
            return

    # Step 1: Check if UID Exists
    try:
        print("[ADMIN] Asking gate guard if UID exists in database...")
        e.send(GATE_GUARD_MAC, b"\x20" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return

    # Wait for reply
    start = time.ticks_ms()
    exists = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x21:  # response to UID check
                exists = msg[1] == 0x01
                break
        time.sleep(0.05)
    if exists is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if exists == 0:
        print("[ADMIN] Card not registered.")
        show_lines(["Card not", "registered"], hold=3)
        show_home()
        return
    else:
        print("[ADMIN] Gate guard says the card exists.")
        pass  # continue

    # Step 2: Ask for card details
    try:
        print("[ADMIN] Asking gate guard for UID info...")
        e.send(GATE_GUARD_MAC, b"\x25" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return

    # Wait for reply
    start = time.ticks_ms()
    readback_status = None
    card_data = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x26:  # response to UID check
                readback_status = msg[1]
                break
        time.sleep(0.05)
    if readback_status is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if readback_status == 0:  # Success
        print("[ADMIN] Readback success.")
        payload_raw = msg[2:].decode().strip()
        payload_clean = extract_json_block(payload_raw)
        if payload_clean is None:
            print("[ADMIN] No valid JSON found.")
            show_lines(["Data error.", "Try again."], hold=3)
            show_home()
            return
        try:
            print(payload_clean)
            print(type(payload_clean))
            card_data = json.loads(payload_clean)  # Returned data as a dictionary
        except Exception as err:
            print(f"[ADMIN] Could not load payload. Error {err}")
            show_lines(["Unknown error.", "Try again."], hold=3)
            show_home()
            return
    elif readback_status == 1:
        print("[ADMIN] Card not registered.")
        show_lines(["Card not", "registered"], hold=3)
        show_home()
        return
    elif readback_status == 2:
        print("[ADMIN] Unknown error occured.")
        show_lines(["Unknown error."], hold=3)
        show_home()
        return
    else:
        show_home()
        return

    for key, value in card_data.items():
        print(f"[ADMIN] Key: {key}, Value: {value}")
        prompt_user(f"{key}: {value}", ["Next"])

    prompt_user("Nothing else to show.", ["End"])
    show_home()
    return


# UPDATE
def update_flow():
    """Update a card's details in the database via Gate Guard."""
    show_lines(["Tap card to", "update..."])
    print("[ADMIN] Waiting for card to be detected.")
    uid = wait_for_card()

    if not uid:
        print("[ADMIN] ❌ No card detected.")
        user_response = None
        user_response = prompt_user("No card detected. Try again?", ["Yes", "No"])
        if user_response == 1:
            print("[ADMIN] Trying to update card again...")
            update_flow()
            return
        elif user_response == 2:
            print("[ADMIN] Register card process cancelled.")
            show_home()
            return
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
            show_home()
            return
    
    # Step 1: Check if UID exists
    try:
        print("[ADMIN] Asking gate guard if UID exists in database...")
        e.send(GATE_GUARD_MAC, b"\x20" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return
    
    # Wait for reply
    start = time.ticks_ms()
    exists = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x21:  # response to UID check
                exists = msg[1] == 0x01
                break
        time.sleep(0.05)
    if exists is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if exists == 0:
        print("[ADMIN] Card not registered.")
        show_lines(["Card not", "registered"], hold=3)
        show_home()
        return
    else:
        pass  # continue

    # Step 3: Get card type
    try:
        print("[ADMIN] Asking gate guard for the UID card type...")
        e.send(GATE_GUARD_MAC, b"\x55" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return
    
    # Wait for reply
    start = time.ticks_ms()
    card_type = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x65:  # response to UID check
                card_type = msg[1]
                break
        time.sleep(0.05)
    if card_type is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if card_type == 0x01:  # monthly card
        print("[ADMIN] Card is said to be monthly type.")
        user_input = prompt_user("Renew monthly card?", ["Yes", "No"])
        if user_input == 1:
            print("[ADMIN] Trying to renew monthly card...")
            renew_err = handle_card_monthly_registration(uid)
            if renew_err == 0:
                show_lines(["Renew", "successful."], hold=3)
            elif renew_err == 1:
                show_lines(["Send failed", "Retry later"], hold=3)
            elif renew_err == 2:
                show_lines(["Could not", "renew"], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 3:
                show_lines(["No response", "from database."], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 4:
                show_lines(["Renew", "failed."], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 5:
                show_lines(["Renew", "cancelled."], hold=3)
        elif user_input == 2:
            print("[ADMIN] Renew card process cancelled.")
            show_lines(["Renew", "cancelled."], hold=3)
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
        show_home()
        return
    elif card_type == 0x02:  # daily card
        print("[ADMIN] Card is said to be daily type.")
        user_input = prompt_user("Renew daily card?", ["Yes", "No"])
        if user_input == 1:
            print("[ADMIN] Trying to renew daily card...")
            renew_err = handle_card_daily_registration(uid)
            if renew_err == 0:
                show_lines(["Renew", "successful."], hold=3)
            elif renew_err == 1:
                show_lines(["Send failed", "Retry later"], hold=3)
            elif renew_err == 2:
                show_lines(["Could not", "renew"], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 3:
                show_lines(["No response", "from database."], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 4:
                show_lines(["Renew", "failed."], hold=3)
                show_lines(["Try again."], hold=3)
            elif renew_err == 5:
                show_lines(["Renew", "cancelled."], hold=3)
        elif user_input == 2:
            print("[ADMIN] Renew card process cancelled.")
            show_lines(["Renew", "cancelled."], hold=3)
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
        show_home()
        return
    elif card_type == 0x03:
        print("[ADMIN] Card is said to be single entry type.")
        will_pay = prompt_user("Pay single entry card?", ["Yes", "No"])
        # handle user input
        if will_pay == 1:
            # get price
            # Paid. Please exit in x mins
            try:
                print("[ADMIN] Asking gate guard for the single entry price...")
                e.send(GATE_GUARD_MAC, b"\x57" + uid.encode())
            except Exception as err:
                print(f"[ADMIN] Error checking if UID exists. {err}")
                show_lines(["ID check failed.", "Try again."], hold=3)
                show_home()
                return
            # Wait for reply
            start = time.ticks_ms()
            get_price_status = None
            while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
                if pending_msgs:
                    mac, msg = pending_msgs.pop(0)
                    if msg[0] == 0x67:
                        get_price_status = msg[1]
                        break
                time.sleep(0.05)
            if get_price_status is None:
                print("[ADMIN] No response from gate guard.")
                show_lines(["No reply", "from database"], hold=3)
            elif get_price_status == 0:
                print(f"[ADMIN] Price gotten. Price - Php {int(msg[2])}")
                prompt_user(f"Your bill is: Php {int(msg[2])}.", ["Ok"])
                prompt_user(f"Paid. Please leave within {GRACE_MINS} mins. Surcharge after grace period.", ["Ok"])
                show_home()
                return
            elif get_price_status == 1:
                print("[ADMIN] Invalid status.")
                status = msg[2:].decode()
                show_lines["Invlaid", "status:", status]
            else:
                pass  # continue
        else:
            show_lines(["Pay", "cancelled."], hold=3)
        show_home()
        return
    elif card_type == 0x04:
        print("[ADMIN] Admin card type gotten")
        prompt_user("Admin card - nothing to update", ["Ok"])
        show_home()
        return
    else:
        print("[ADMIN] Unknown card type")
        prompt_user("Unknown card type.", ["Ok"])
        show_home()
        return


# DELETE
def delete_flow():
    """Delete a card from the database via Gate Guard."""
    show_lines(["Tap card to", "delete..."])
    uid = wait_for_card()

    if not uid:
        print("[ADMIN] ❌ No card detected.")
        user_response = None
        user_response = prompt_user("No card detected. Try again?", ["Yes", "No"])
        if user_response == 1:
            print("[ADMIN] Trying to register card again...")
            register_flow()
            return
        elif user_response == 2:
            print("[ADMIN] Register card process cancelled.")
            show_home()
            return
        else:
            print("[ADMIN] Wrong button pressed")
            show_lines(["Unknown command.", "Try again."], hold=3)
            show_home()
            return

    # Step 1: Check if UID exists
    try:
        print("[ADMIN] Asking gate guard if UID exists in database...")
        e.send(GATE_GUARD_MAC, b"\x20" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] Error checking if UID exists. {err}")
        show_lines(["ID check failed.", "Try again."], hold=3)
        show_home()
        return

    # Wait for reply
    start = time.ticks_ms()
    exists = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x21:  # response to UID check
                exists = msg[1] == 0x01
                break
        time.sleep(0.05)
    if exists is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
        show_home()
        return
    if exists == 0:
        print("[ADMIN] Card not registered.")
        show_lines(["Card not", "registered"], hold=3)
        show_home()
        return
    else:
        pass  # continue

    # Step 2: Ask for certain of card should be deleted
    user_response = None
    user_response = prompt_user(
        "Card found. Are you sure you want to delete card?", ["Yes", "No"]
    )
    if user_response == 1:
        print("[ADMIN] Trying to delete card.")
        show_lines(["Deleting card", "from database."])
    elif user_response == 2:
        print("[ADMIN] Cancelled card deletion.")
        show_lines(["Card deletion", "cancelled."])
        show_home()
        return
    else:
        print("[ADMIN] Wrong button pressed")
        show_lines(["Unknown command.", "Try again."], hold=3)
        show_home()
        return

    # Step 3: Ask the gate guard to delete UID
    try:
        print(f"[ADMIN] 📨 Sending delete request for UID={uid}")
        e.send(GATE_GUARD_MAC, b"\x24" + uid.encode())
    except Exception as err:
        print(f"[ADMIN] ⚠️ Error sending delete request: {err}")
        show_lines(["Delete failed.", "Send error"], hold=3)
        show_home()
        return

    # Wait for reply
    start = time.ticks_ms()
    delete_status = None
    while time.ticks_diff(time.ticks_ms(), start) < 3000:  # 3s timeout
        if pending_msgs:
            mac, msg = pending_msgs.pop(0)
            if msg[0] == 0x25:  # response to UID check
                delete_status = msg[1]
                break
        time.sleep(0.05)
    if delete_status is None:
        print("[ADMIN] No response from gate guard.")
        show_lines(["No reply", "from database"], hold=3)
    if delete_status == 0:
        print("[ADMIN] Card was said to be deleted.")
        show_lines(["Card deleted."], hold=3)
    elif delete_status == 1:
        print("[ADMIN] Card not registered.")
        show_lines(["Card not", "registered"], hold=3)
    elif delete_status == 2:
        print("[ADMIN] Unknown error occured.")
        show_lines(["Unknown error."], hold=3)
    elif delete_status == 3:
        print("[ADMIN] Card is not yet paid.")
        show_lines(["Card not paid.", "Please pay first."], hold=3)

    show_home()
    return


def extract_json_block(data_str):
    start = data_str.find("{")
    end = data_str.find("}", start)
    if start != -1 and end != -1:
        return data_str[start : end + 1]  # include the closing }
    return None


# ---- RFID HELPERS ---


def wait_for_card(timeout=10000):
    """
    Block until a card UID is read from MFRC522 or timeout expires.
    timeout default = 10s
    Returns UID string like '0x43EA1AD86B' or None.
    """
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < timeout:
        (stat, tag_type) = rfid.request(rfid.REQIDL)
        if stat == rfid.OK:
            (stat, raw_uid) = rfid.anticoll()
            if stat == rfid.OK:
                uid_str = "0x" + "".join("{:02X}".format(i) for i in raw_uid)
                print(f"[READER] Detected card UID={uid_str}")
                return uid_str
    return None


# ---- TIME HELPERS ----


def get_local_time_s():
    """Get local time in seconds since epoch adjusted for UTC offset"""
    return time.time() + UTC_OFFSET


def get_local_time(local_time_s: float = None):
    """Return localtime tuple adjusted for UTC offset"""
    if local_time_s is None:
        local_time_s = get_local_time_s()
    return time.localtime(local_time_s)


def format_time(ts=None):
    """Returns formatted time string for a timestamp (or now if ts None)."""
    if ts is None:
        ts = get_local_time_s()
    # Use time.localtime to get tuple, then format
    y, m, d, hh, mm, ss, _, _ = time.localtime(ts)
    return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}"


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
show_lines(
    ["WiFi Connected", sta_if.ifconfig()[0], f"Channel: {sta_if.config('channel')}"],
    hold=3,
)

# Sync time from NTP
if not do_sync_time_online(NTP_SERVERS):
    raise Exception("Could not sync time on startup")

print(f"[ADMIN] Current date/time: {get_local_time()}")
show_lines(
    ["Time Synced", str(get_local_time()[0:3]), str(get_local_time()[3:6])], hold=3
)

# Init ESP-NOW
e = espnow.ESPNow()
e.active(True)
e.add_peer(GATE_GUARD_MAC)


def recv_cb(e):
    global pending_msgs
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
                show_lines(["Time Sent", "to Gate Guard"], hold=3)
                show_home()
            elif msg[0] == 0x21:  # Guard response to checking if UID exists
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x23:  # Guard response to for monthly registration
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x62:  # Guard response to for daily registration
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x63:  # Guard response to for single entry registration
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x65:  # Guard response to get card type
                print(f"[ADMIN] Gate Guard replied card type {msg[1]}")
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x67:  # Guard response to get card price
                print(f"[ADMIN] Gate Guard replied card price with status {msg[1]}")
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x25:  # Guard response to UID deletion
                pending_msgs.append((mac, msg))
            elif msg[0] == 0x26:  # Guard response to UID read
                pending_msgs.append((mac, msg))
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


# --- after setup + time sync success ---
def show_home():
    global last_button_pressed
    last_button_pressed = None
    show_lines(["[B1]Register", "[B2]Read", "[B3]Update", "[B4]Delete"])


show_home()

# ---- MAIN LOOP ----
while True:
    if last_button_pressed is not None:
        # Map gpio to button id
        btn_id = BUTTON_PINS[last_button_pressed]
        last_button_pressed = None
        print(f"[ADMIN] Button event in main loop: btn_id={btn_id}")
        if btn_id == 1:
            # Register
            register_flow()
        elif btn_id == 2:
            read_flow()
        elif btn_id == 3:
            update_flow()
        elif btn_id == 4:
            delete_flow()
        else:
            # Unknown: show home
            show_home()
    time.sleep(0.1)
