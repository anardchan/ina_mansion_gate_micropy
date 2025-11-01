import espnow  # type: ignore
import network  # type: ignore
import time
import struct
import json
import os
from machine import Timer  # type: ignore
from config import (
    ADMIN_MAC,
    MAX_LOG_LINES,
    INSIDE_READER_MAC,
    OUTSIDE_READER_MAC,
    UTC_OFFSET,
    CAR_SINGLE_ENTRY_RATE_FIRST_HOURS,
    CAR_SINGLE_ENTRY_FIRST_HOURS_DURATION,
    CAR_SINGLE_ENTRY_EXTRA_HOUR_RATE,
    MOTOR_SINGLE_ENTRY_FIRST_HOURS_DURATION,
    MOTOR_SINGLE_ENTRY_RATE_FIRST_HOURS,
    MOTOR_SINGLE_ENTRY_EXTRA_HOUR_RATE,
    GRACE_MINS,
    CHANNEL,
    RUNNER_E_MAC,
    SSID,
    SSID_PW,
    NTP_SERVERS,
)

# ---- FILES ----
DB_FILE = "database.json"
LOG_FILE = "logs/access_log.txt"

# ---- ERROR CODES (constants) ----
ERR_SUCCESS = 0x00
ERR_NOT_FOUND = 0x01
ERR_EXPIRED = 0x02
ERR_WRONG_DIRECTION = 0x03
ERR_ALREADY_USED = 0x04
ERR_NOT_IN_PROGRESS = 0x05
ERR_GRACE_EXPIRED = 0x06
ERR_PAYMENT_PROCESSED = 0x07
ERR_UNKNOWN_READER = 0x08

ERROR_DESCRIPTIONS = {
    ERR_SUCCESS: "Success",
    ERR_NOT_FOUND: "Card not found",
    ERR_EXPIRED: "Card expired",
    ERR_WRONG_DIRECTION: "Wrong direction (must alternate in/out)",
    ERR_ALREADY_USED: "Already used",
    ERR_NOT_IN_PROGRESS: "Not in progress (no entry recorded)",
    ERR_GRACE_EXPIRED: "Grace period expired",
    ERR_PAYMENT_PROCESSED: f"Payment processed — grace period started ({GRACE_MINS} min)",
    ERR_UNKNOWN_READER: "Unknown reader MAC",
}

# ---- GLOBAL STATE ----
local_time_offset = None  # correction offset from board RTC to synced local time


# ---- TIME HELPERS ----
def get_local_time_s():
    """Return local time in seconds since epoch (with UTC offset + correction)."""
    if local_time_offset is None:
        return time.time() + UTC_OFFSET
    return time.time() + UTC_OFFSET + local_time_offset


def get_local_time():
    """Return local time tuple adjusted for offset."""
    return time.localtime(get_local_time_s())


def format_time(ts=None):
    """Returns formatted time string for a timestamp (or now if ts None)."""
    if ts is None:
        ts = get_local_time_s()
    # Use time.localtime to get tuple, then format
    y, m, d, hh, mm, ss, _, _ = time.localtime(ts)
    return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}"


# ---- DATABASE HANDLERS ----
def init_db():
    """Create empty DB file if it doesn't exist."""
    if DB_FILE not in os.listdir():
        db = {"monthly": {}, "daily": {}, "single_entry": {}}
        save_db(db)
        print("[DB] Created new database.json")


def load_db():
    """Load DB from storage. Assumes init_db() already ran."""
    try:
        with open(DB_FILE, "r") as f:
            db = json.load(f)
            return db
    except Exception as e:
        print("[DB] Error loading DB:", e)
        # Recreate DB to avoid crashes
        db = {"monthly": {}, "daily": {}, "single_entry": {}}
        save_db(db)
        return db


def save_db(db):
    """Save DB to storage (atomic not implemented)."""
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f)
    except Exception as e:
        print("[DB] Error saving DB:", e)


# ---- LOGGING ----
def ensure_logs_dir():
    try:
        if "logs" not in os.listdir():
            os.mkdir("logs")
    except Exception:
        # ignore if it already exists or cannot create
        pass


def trim_log_file():
    """
    Keep only the last MAX_LOG_LINES lines in the log file.
    Called before appending a new entry.
    """
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            # Keep only the last MAX_LOG_LINES lines
            lines = lines[-MAX_LOG_LINES:]
            with open(LOG_FILE, "w") as f:
                f.writelines(lines)
    except OSError:
        # file doesn't exist yet
        pass


def log_access(message, err_code=None):
    """
    Append human-readable guard-style log entry.
    If err_code provided, include description.
    """
    ensure_logs_dir()  # ensure log file exists
    trim_log_file()  # ensure rolling log
    if err_code is not None:
        desc = ERROR_DESCRIPTIONS.get(err_code, "Unknown error")
        entry = f"{message} (err=0x{err_code:02X} - {desc})"
    else:
        entry = message

    timestamp = format_time()
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {entry}\n")
    # Also print to console (debug)
    print(f"[ACCESS LOG] [{timestamp}] {entry}")


# ---- SINGLE ENTRY BILLING ----
def complete_single_entry(uid):
    """
    Called when payment is made (user pays on exit). This sets:
      - exit_time = payment timestamp (readable string)
      - expiration_time = payment_time + 20 minutes (grace period)
      - price = computed price
      - status = 'paid'
    Returns computed price (int).
    """
    db = load_db()
    card = db["single_entry"].get(uid)
    if not card:
        print("[BILL] complete_single_entry called for unknown UID", uid)
        return None

    pay_time = get_local_time_s()
    readable_now = format_time(pay_time)

    # entry_time must exist (in_progress)
    try:
        # Split date and time
        date_str, time_str = card["entry_time"].split(" ")
        year, month, day = map(int, date_str.split("-"))
        hour, minute, second = map(int, time_str.split(":"))
        # Build the full 8-tuple required by mktime
        # (year, month, mday, hour, minute, second, weekday, yearday)
        # weekday (-1) and yearday (-1) can be placeholders in MicroPython
        tm_tuple = (year, month, day, hour, minute, second, -1, -1)

        entry_s = time.mktime(tm_tuple)
    except Exception:
        # fallback if entry_time missing/invalid
        entry_s = pay_time

    # Ceil hours: (diff + 3599) // 3600
    duration_h = int((pay_time - entry_s + 3599) // 3600)

    if card["vehicle_type"] == "car":
        first_hours_duration = CAR_SINGLE_ENTRY_FIRST_HOURS_DURATION
        rate_first_hours = CAR_SINGLE_ENTRY_RATE_FIRST_HOURS
        extra_hour_rate = CAR_SINGLE_ENTRY_EXTRA_HOUR_RATE
    else:
        first_hours_duration = MOTOR_SINGLE_ENTRY_FIRST_HOURS_DURATION
        rate_first_hours = MOTOR_SINGLE_ENTRY_RATE_FIRST_HOURS
        extra_hour_rate = MOTOR_SINGLE_ENTRY_EXTRA_HOUR_RATE

    if duration_h <= first_hours_duration:
        price = rate_first_hours
    else:
        extra_h = duration_h - first_hours_duration
        price = rate_first_hours + extra_h * extra_hour_rate

    card["exit_time"] = readable_now
    card["expiration_time"] = format_time(pay_time + (GRACE_MINS * 60))
    card["price"] = price
    card["status"] = "paid"
    save_db(db)
    print(
        f"[BILL] UID {uid} payment recorded. Price={price}, grace until {card['expiration_time']}"
    )
    log_access(
        f"UID {uid} payment processed — Price={price}, vehicle type = {card["vehicle_type"]}", err_code=ERR_PAYMENT_PROCESSED
    )
    return price


# ---- VALIDATION / ACCESS LOGIC ----
def validate_card(uid, source_mac):
    """
    Validate card request from a reader.

    Returns: (approved: bool, err_code: int)
      - If approved True, err_code == ERR_SUCCESS.
      - If not approved, err_code explains why (see ERROR_DESCRIPTIONS).
    """
    db = load_db()
    now = get_local_time_s()
    readable_now = format_time(now)

    # Determine direction based on reader MAC
    if source_mac == INSIDE_READER_MAC:
        direction = "out"
    elif source_mac == OUTSIDE_READER_MAC:
        direction = "in"
    else:
        # Unknown reader
        print("[GATE GUARD] Unknown reader MAC:", source_mac)
        log_access(
            f"UID {uid} denied — unknown reader {source_mac}",
            err_code=ERR_UNKNOWN_READER,
        )
        return False, ERR_UNKNOWN_READER

    # Find card in DB
    found_card = None
    card_type = None
    for ctype in ("admin", "monthly", "daily", "single_entry"):
        if uid in db.get(ctype, {}):
            found_card = db[ctype][uid]
            card_type = ctype
            break

    if not found_card:
        log_access(f"UID {uid} denied — not found", err_code=ERR_NOT_FOUND)
        return False, ERR_NOT_FOUND

    # Admin card behavior
    if card_type in ("admin"):
        log_access(f"UID {uid} approved (admin)")
        return True, ERR_SUCCESS

    # Automatic expiration check: if status is expired, deny
    if found_card.get("status") == "expired":
        if card_type == "single_entry":
            log_access(
                f"UID {uid} denied — grace period expired", err_code=ERR_GRACE_EXPIRED
            )
            log_access(
                f"UID {uid} details. Time paid: {found_card['exit_time']} . Valid unitl: {found_card['expiration_time']}"
            )
        else:
            log_access(f"UID {uid} denied — expired", err_code=ERR_EXPIRED)
        return False, ERR_EXPIRED

    # Monthly behavior
    if card_type in ("monthly"):
        if found_card.get("status") == "new":
            # Set the initial io_status
            found_card["io_status"] = direction
            found_card["status"] = "active"
            log_access(f"UID {uid} new. Set initial io_status ({direction})")
            log_access(f"UID {uid}. Set status to active")
        else:
            # io_status holds last action; incoming request must be opposite
            last_io = found_card.get("io_status")
            if last_io == direction:
                # same direction twice -> denied
                log_access(
                    f"UID {uid} denied — wrong direction ({direction})",
                    err_code=ERR_WRONG_DIRECTION,
                )
                return False, ERR_WRONG_DIRECTION
            else:
                # Flip io_status
                found_card["io_status"] = direction
        # Approve
        save_db(db)
        log_access(f"UID {uid} approved ({card_type}, {direction})")
        return True, ERR_SUCCESS

    # Daily behavior
    if card_type in ("daily"):
        if found_card.get("status") == "new":
            # Set the initial io_status
            found_card["io_status"] = direction
            found_card["status"] = "active"
            log_access(f"UID {uid} new. Set initial io_status ({direction})")
            log_access(f"UID {uid}. Set status to active")
        else:
            pass
            # io_status holds last action; incoming request must be opposite
            last_io = found_card.get("io_status")
            if last_io == direction:
                # same direction twice -> denied
                log_access(
                    f"UID {uid} denied — wrong direction ({direction})",
                    err_code=ERR_WRONG_DIRECTION,
                )
                return False, ERR_WRONG_DIRECTION
            else:
                # Flip io_status
                found_card["io_status"] = direction
        # Approve
        save_db(db)
        log_access(f"UID {uid} approved ({card_type}, {direction})")
        return True, ERR_SUCCESS

    # Single-entry behavior
    if card_type == "single_entry":
        status = found_card.get("status", "new")

        # IN path: registration of entry
        if direction == "in":
            if status == "new":
                # mark entry
                found_card["entry_time"] = readable_now
                found_card["status"] = "in_progress"
                found_card["io_status"] = "in"
                save_db(db)
                log_access(f"UID {uid} approved — checked IN (single_entry)")
                return True, ERR_SUCCESS
            else:
                # Already used / in_progress / paid / completed -> deny
                log_access(
                    f"UID {uid} denied — already used", err_code=ERR_ALREADY_USED
                )
                return False, ERR_ALREADY_USED

        # OUT path: several possibilities
        else:  # direction == "out"
            if status == "paid":
                # check grace period
                exp_str = found_card.get("expiration_time")
                if not exp_str:
                    # malformed: treat as expired
                    found_card["status"] = "expired"
                    save_db(db)
                    log_access(
                        f"UID {uid} denied — grace info missing",
                        err_code=ERR_GRACE_EXPIRED,
                    )
                    return False, ERR_GRACE_EXPIRED

                try:
                    # Split date and time
                    date_str, time_str = exp_str.split(" ")
                    year, month, day = map(int, date_str.split("-"))
                    hour, minute, second = map(int, time_str.split(":"))
                    # Build the full 8-tuple required by mktime
                    # (year, month, mday, hour, minute, second, weekday, yearday)
                    # weekday (-1) and yearday (-1) can be placeholders in MicroPython
                    tm_tuple = (year, month, day, hour, minute, second, -1, -1)
                    exp_s = time.mktime(tm_tuple)
                except Exception:
                    # bad format -> expire
                    found_card["status"] = "expired"
                    save_db(db)
                    log_access(
                        f"UID {uid} denied — grace parse error",
                        err_code=ERR_GRACE_EXPIRED,
                    )
                    return False, ERR_GRACE_EXPIRED

                if now <= exp_s:
                    # allow exit
                    found_card["status"] = "completed"
                    found_card["io_status"] = "out"
                    save_db(db)
                    log_access(f"UID {uid} approved — exited within grace period")

                    # --- delete card from database ---
                    try:
                        del db[ctype][uid]
                        save_db(db)
                        log_access(f"UID {uid} deleted from database after exit")
                    except KeyError:
                        log_access(f"UID {uid} not found in database for deletion")

                    return True, ERR_SUCCESS
                else:
                    # grace expired
                    found_card["status"] = "expired"
                    save_db(db)
                    log_access(
                        f"UID {uid} denied — grace period expired",
                        err_code=ERR_GRACE_EXPIRED,
                    )
                    return False, ERR_GRACE_EXPIRED

            elif status == "completed":
                # already finished
                log_access(
                    f"UID {uid} denied — already completed", err_code=ERR_ALREADY_USED
                )
                return False, ERR_ALREADY_USED

            else:
                # status is 'new' or others (not in_progress and not paid)
                log_access(
                    f"UID {uid} denied — not in progress", err_code=ERR_NOT_IN_PROGRESS
                )
                return False, ERR_NOT_IN_PROGRESS

    # Fallback deny
    log_access(f"UID {uid} denied — unknown condition", err_code=ERR_NOT_FOUND)
    return False, ERR_NOT_FOUND


# ---- ESP-NOW ----

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.STA_IF)  # Or network.WLAN.IF_AP
sta.active(True)
time.sleep_ms(200)  # <-- Give Wi-Fi hardware time to settle

try:
    sta.config(channel=CHANNEL)
except Exception as ex:
    print("[WARN] Failed to set Wi-Fi channel initially:", ex)
    # Retry once after short delay
    time.sleep_ms(500)
    try:
        sta.config(channel=CHANNEL)
    except Exception as ex2:
        print("[ERROR] Second attempt to set channel failed:", ex2)

sta.disconnect()

e = espnow.ESPNow()
e.active(True)
# Add peers we expect to communicate with (best-effort)
try:
    e.add_peer(ADMIN_MAC)
except Exception:
    pass
try:
    e.add_peer(INSIDE_READER_MAC)
except Exception:
    pass
try:
    e.add_peer(OUTSIDE_READER_MAC)
except Exception:
    pass
try:
    e.add_peer(RUNNER_E_MAC)
except Exception:
    pass


def request_time_from_admin():
    """Send a time sync request to the admin board."""
    print("[GATE GUARD] ⏳ Requesting time from Admin...")
    try:
        e.send(ADMIN_MAC, b"\x0c")
    except Exception as ex:
        print("[GATE GUARD] Failed to send time request:", ex)


def handle_delete_request(mac, msg):
    """Handle delete request from Admin Board."""
    db = load_db()
    try:
        uid = msg[1:].decode()
        log_access(f"[GATE_GUARD] 🗑️ Delete request for UID={uid}")

        found = False
        for section in ["admin", "monthly", "daily", "single_entry"]:
            if uid in db.get(section, {}):
                print(f"section: {section}")
                if section == "single_entry":
                    print(f"Card status : {db[section][uid]["status"]}")
                    if db[section][uid]["status"] == "paid" or db[section][uid]["status"] == "new" or db[section][uid]["status"] == "expired" :
                        # Paid, can delete card if wished
                        del db[section][uid]
                        save_db(db)
                        log_access(f"[GATE_GUARD] ✅ UID {uid} deleted from {section}.")
                        e.send(mac, b"\x25\x00")  # success deletion
                    else: 
                        # Not paid, cannot delete card
                        log_access(f"[GATE_GUARD] ‼️ UID {uid} cannot be deleted from {section}. Not yet paid!")
                        e.send(mac, b"\x25\x03")  # Cannot be deleted
                else: # monthly or daily card
                    del db[section][uid]
                    save_db(db)
                    log_access(f"[GATE_GUARD] ✅ UID {uid} deleted from {section}.")
                    e.send(mac, b"\x25\x00")  # success deletion
                found = True
                break
        if not found:
            log_access(f"[GATE_GUARD] ❌ UID {uid} not found in DB.")
            e.send(mac, b"\x25\x01")  # Card not found

    except Exception as err:
        log_access(f"[GATE_GUARD] ⚠️ Error handling delete: {err}")
        e.send(mac, b"\x25\x02")  # generic error


def handle_read_request(mac, msg):
    """Handle read request from Admin Board."""
    db = load_db()
    try:
        uid = msg[1:].decode()
        log_access(f"[GATE_GUARD] 👓 Read request for UID={uid}")

        found = False
        for section in ["admin", "monthly", "daily", "single_entry"]:
            if uid in db.get(section, {}):
                # Build card info
                card_data = {}
                card_data.clear()
                card_data["ID"] = uid
                for key, value in db[section][uid].items():
                    card_data[key] = value
                print(card_data)
                # Send to Admin
                try:
                    payload = json.dumps(card_data)
                    if len(payload) > 240:
                        log_access(
                            "[GATE_GUARD] ⚠️ Error handling read: data too long to send"
                        )
                        e.send(mac, b"\x26\x02")
                        return
                    print("Sending data to Admin")
                    e.send(
                        mac, b"\x26\x00" + payload.encode()
                    )  # success read and try sending data
                except Exception:
                    log_access("[GATE_GUARD] Failed to send UID data")
                    return
                log_access("[GATE_GUARD] UID details sent back to admin.")
                found = True
                print(f"Found status is {found}")
                break

        if not found:
            log_access(f"[GATE_GUARD] ❌ UID {uid} not found in DB.")
            e.send(mac, b"\x26\x01")  # Card not found
            return

    except Exception as err:
        log_access(f"[GATE_GUARD] ⚠️ Error handling read: {err}")
        e.send(mac, b"\x26\x02")  # generic error

    return


def recv_cb(e):
    """ESP-NOW interrupt callback. Handles: time sync responses, reader requests."""
    global local_time_offset
    while True:
        mac, msg = e.irecv(0)
        if mac is None:
            break

        # Time sync response from admin
        if mac == ADMIN_MAC and msg and msg[0] == 0x0C:
            try:
                received_time = struct.unpack("I", msg[1:])[0]
                local_time_offset = received_time - (time.time() + UTC_OFFSET)
                print(f"[GATE GUARD] ✅ Time updated from Admin: {get_local_time()}")
                log_access("Time sync from admin")
            except Exception as ex:
                print("[GATE GUARD] Bad time response:", ex)
                log_access("Bad time response from admin")

        # Reader access request
        elif mac == RUNNER_E_MAC and msg and msg[0] == 0x10:
            try:
                uid = msg[2:].decode()
            except Exception:
                uid = ""
            
            reader = ""
            if msg[1] == 0x0a:
                reader = "inside reader"
                mac_reader = INSIDE_READER_MAC
            elif msg[1] == 0x0b:
                reader = "outside reader"
                mac_reader = OUTSIDE_READER_MAC

            print(f"[GATE GUARD] 📩 Access request from {reader}, UID={uid}")
            approved, err = validate_card(uid, mac_reader)
            # Approved: send 0x11 0x01
            if approved:
                try:
                    e.send(mac, b"\x11" + b"\x01")
                except Exception as ex:
                    print("[GATE GUARD] Failed to send approval:", ex)
                # Debug log already created inside validate_card
            else:
                # Denied: send 0x11 0x00 <err_code>
                try:
                    e.send(mac, b"\x11" + b"\x00" + bytes([err]))
                except Exception as ex:
                    print("[GATE GUARD] Failed to send denial:", ex)
                # Also include error description in the log (validate_card already logged)
                print(
                    f"[GATE GUARD] Decision: DENIED err=0x{err:02X} - {ERROR_DESCRIPTIONS.get(err, '?')}"
                )

        # Admin: Check if UID exists
        elif mac == ADMIN_MAC and msg and msg[0] == 0x20:
            try:
                print(f"msg : {msg}")
                print(f"msg_hex : {msg.hex()}")
                uid = msg[1:].decode()
                print(f"Admin: Check if UID {uid} exists")
                db = load_db()
                exists = any(
                    uid in db[ctype]
                    for ctype in ("admin", "monthly", "daily", "single_entry")
                )
                if exists:
                    e.send(ADMIN_MAC, b"\x21\x01")
                    log_access(f"Admin checked UID {uid}: already exists")
                else:
                    e.send(ADMIN_MAC, b"\x21\x00")
                    log_access(f"Admin checked UID {uid}: not found.")
            except Exception as ex:
                print("[GATE GUARD] UID check failed:", ex)

        # Admin: Get card type
        elif mac == ADMIN_MAC and msg and msg[0] == 0x55:
            try:
                uid = msg[1:].decode()
                db = load_db()
                uid_found = False
                for c_type in ["admin", "monthly", "daily", "single_entry"]:
                    if uid in db.get(c_type):
                        if c_type == "monthly":
                            log_access("UID type: monthly. Sent to Admin.")
                            e.send(ADMIN_MAC, b"\x65\x01")
                        elif c_type == "daily":
                            log_access("UID type: daily. Sent to Admin.")
                            e.send(ADMIN_MAC, b"\x65\x02")
                        elif c_type == "single_entry":
                            log_access("UID type: single_entry. Sent to Admin.")
                            e.send(ADMIN_MAC, b"\x65\x03")
                        elif c_type == "admin":
                            log_access("UID type: single_entry. Sent to Admin.")
                            e.send(ADMIN_MAC, b"\x65\x04")
                        uid_found = True
                        break
                if not uid_found:
                    log_access("UID type: not found. Sent to Admin.")
                    e.send(ADMIN_MAC, b"\x65\x00")
            except Exception as ex:
                log_access("UID check type failed:", ex)
        
        # Admin: Get vehicle type
        elif mac == ADMIN_MAC and msg and msg[0] == 0x59:
            try:
                uid = msg[1:].decode()
                db = load_db()
                uid_found = False
                for c_type in ["admin", "monthly", "daily", "single_entry"]:
                    if uid in db.get(c_type):
                        if c_type == "monthly" or c_type=="daily" or c_type=="single_entry":
                            vehicle_t = db[c_type][uid]["vehicle_type"]
                            if vehicle_t == "car":
                                log_access("UID vehicle type: Car. Sent to Admin.")
                                e.send(ADMIN_MAC, b"\x69\x01")
                            else:
                                log_access("UID vehicle type: Motorcycle. Sent to Admin.")
                                e.send(ADMIN_MAC, b"\x69\x02")
                        elif c_type == "admin":
                            log_access("UID vehicle type: N/A (admin). Sent to Admin.")
                            e.send(ADMIN_MAC, b"\x69\x00")
                        uid_found = True
                        break
                if not uid_found:
                    log_access("UID type: not found. Sent to Admin.")
                    e.send(ADMIN_MAC, b"\x69\x03")
            except Exception as ex:
                log_access("UID check vehicle type failed:", ex)
        
        # Admin: Get single entry price type
        elif mac == ADMIN_MAC and msg and msg[0] == 0x57:
            try:
                uid = msg[1:].decode()
                db = load_db()
                card = db["single_entry"][uid]
                status = card.get("status")
                if status == "in_progress":
                    # This is the payment moment: complete_single_entry sets 'paid' and grace
                    price = complete_single_entry(uid)
                    # complete_single_entry already logged payment
                    e.send(ADMIN_MAC, b"\x67\x00"+price.to_bytes())
                    log_access(f"💰 UID price sent: Php {price}")
                else:
                    e.send(ADMIN_MAC, b"\x67\x01"+status.encode())
                    log_access(f"Invalid UID status for payment: {status}")
            except Exception as ex:
                print("Send price failed:", ex)

        # Admin: Register monthly card
        elif mac == ADMIN_MAC and msg and msg[0] == 0x22:
            try:
                payload = msg[1:].decode()
                card_data = json.loads(payload)
                db = load_db()
                uid = card_data["uid"]
                db["monthly"][uid] = {
                    "vehicle_type": card_data["vehicle_type"],
                    "activation_time": card_data["activation_time"],
                    "expiration_time": card_data["expiration_time"],
                    "io_status": "out",
                    "status": "new",
                }
                save_db(db)
                e.send(ADMIN_MAC, b"\x23\x00")
                log_access(f"UID {uid} registered (monthly)")
            except Exception as ex:
                print("[GATE GUARD] Register monthly failed:", ex)
                try:
                    e.send(ADMIN_MAC, b"\x23\x01")
                except:
                    pass
                log_access("Register monthly failed", err_code=ERR_NOT_FOUND)
        
        # Admin: Register daily card
        elif mac == ADMIN_MAC and msg and msg[0] == 0x52:
            try:
                payload = msg[1:].decode()
                card_data = json.loads(payload)
                db = load_db()
                uid = card_data["uid"]
                db["daily"][uid] = {
                    "vehicle_type": card_data["vehicle_type"],
                    "activation_time": card_data["activation_time"],
                    "expiration_time": card_data["expiration_time"],
                    "io_status": "out",
                    "status": "new",
                }
                save_db(db)
                e.send(ADMIN_MAC, b"\x62\x00")
                log_access(f"UID {uid} registered (daily)")
            except Exception as ex:
                print("[GATE GUARD] Register daily failed:", ex)
                try:
                    e.send(ADMIN_MAC, b"\x62\x01")
                except:
                    pass
                log_access("Register daily failed", err_code=ERR_NOT_FOUND)

        # Admin: Register Single Entry Card
        elif mac == ADMIN_MAC and msg and msg[0] == 0x53:
            try:
                payload = msg[1:].decode()
                card_data = json.loads(payload)
                db = load_db()
                uid = card_data["uid"]
                db["single_entry"][uid] = {
                    "vehicle_type": card_data["vehicle_type"],
                    "entry_time": card_data["entry_time"],
                    "io_status": card_data["io_status"],
                    "status": card_data["status"],
                }
                save_db(db)
                e.send(ADMIN_MAC, b"\x63\x00")
                log_access(f"UID {uid} registered (single entry)")
            except Exception as ex:
                print("[GATE GUARD] Register single entry failed:", ex)
                try:
                    e.send(ADMIN_MAC, b"\x63\x01")
                except:
                    pass
                log_access("Register single entry failed", err_code=ERR_NOT_FOUND)


        elif mac == ADMIN_MAC and msg and msg[0] == 0x24:  # Delete request
            handle_delete_request(mac, msg)

        elif mac == ADMIN_MAC and msg and msg[0] == 0x25:  # Read request
            handle_read_request(mac, msg)

        else:
            print("[GATE GUARD] ❓ Unknown message or source:", mac, msg)


# register IRQ callback
e.irq(recv_cb)

# ---- STARTUP: ensure DB exists and sync time ----
init_db()
print("[GATE GUARD] DB initialized.")
print("[GATE GUARD] Waiting for boot time sync from admin...")

# Block until we get local_time_offset (strict requirement)
while local_time_offset is None:
    request_time_from_admin()
    time.sleep(2)  # wait before retrying

print("[GATE GUARD] Boot time synchronized:", get_local_time())
log_access("Boot time synchronized")

# Debug dump of DB (print top-level counts)
db = load_db()
print(
    "[DB] Summary: admin=%d, monthly=%d, daily=%d, single_entry=%d"
    % (
        len(db.get("admin", {})),
        len(db.get("monthly", {})),
        len(db.get("daily", {})),
        len(db.get("single_entry", {})),
    )
)
log_access(
    f"DB summary: admin={len(db.get('admin', {}))}, monthly={len(db.get('monthly', {}))}, daily={len(db.get('daily', {}))}, single_entry={len(db.get('single_entry', {}))}"
)


# ---- WEEKLY RESYNC (best-effort) ----
def weekly_resync(timer):
    tm = get_local_time()
    # Sunday = 6, 4:00 AM = hour=4, min=0
    if tm[6] == 6 and tm[3] == 4 and tm[4] == 0:
        request_time_from_admin()


weekly_timer = Timer(0)
weekly_timer.init(period=60000, mode=Timer.PERIODIC, callback=weekly_resync)


# ---- PERIODIC MAINTENANCE: expire cards every minute ----
def expire_cards(timer):
    db = load_db()
    now = get_local_time_s()
    changed = False

    # monthly
    for uid, card in list(db.get("monthly", {}).items()):
        exp_str = card.get("expiration_time")
        if exp_str:
            try:
                # Split date and time
                date_str, time_str = exp_str.split(" ")
                year, month, day = map(int, date_str.split("-"))
                hour, minute, second = map(int, time_str.split(":"))
                # Build the full 8-tuple required by mktime
                # (year, month, mday, hour, minute, second, weekday, yearday)
                # weekday (-1) and yearday (-1) can be placeholders in MicroPython
                tm_tuple = (year, month, day, hour, minute, second, -1, -1)

                exp_s = time.mktime(tm_tuple)
                if now >= exp_s and card.get("status") != "expired":
                    card["status"] = "expired"
                    log_access(
                        f"UID {uid} auto-expired (monthly)", err_code=ERR_EXPIRED
                    )
                    changed = True
            except Exception:
                # ignore parse errors
                pass

    # daily
    for uid, card in list(db.get("daily", {}).items()):
        exp_str = card.get("expiration_time")
        if exp_str:
            try:
                # Split date and time
                date_str, time_str = exp_str.split(" ")
                year, month, day = map(int, date_str.split("-"))
                hour, minute, second = map(int, time_str.split(":"))
                # Build the full 8-tuple required by mktime
                # (year, month, mday, hour, minute, second, weekday, yearday)
                # weekday (-1) and yearday (-1) can be placeholders in MicroPython
                tm_tuple = (year, month, day, hour, minute, second, -1, -1)

                exp_s = time.mktime(tm_tuple)
                if now >= exp_s and card.get("status") != "expired":
                    card["status"] = "expired"
                    log_access(f"UID {uid} auto-expired (daily)", err_code=ERR_EXPIRED)
                    changed = True
            except Exception:
                pass

    if changed:
        save_db(db)


maintenance_timer = Timer(1)
maintenance_timer.init(period=60000, mode=Timer.PERIODIC, callback=expire_cards)

# --- DEBUG HELPER ---


def print_database():
    try:
        with open("database.json", "r") as f:
            data = json.load(f)
            print("JSON contents:")
            print(json.dumps(data))
    except OSError:
        print("Error: 'database.json' not found or could not be opened.")
    except ValueError:
        print("Error: 'database.json' contains invalid JSON data.")


def print_log_file():
    try:
        with open("logs/access_log.txt", "r") as f:
            file_content = f.read()
            # Print the content
            print("--- Guard Log File Contents ---")
            print(file_content)
            print("--------------------")
    except OSError as e:
        print(f"Error accessing file 'logs/access_log.txt': {e}")


# ---- MAIN LOOP (heartbeat) ----
# while True:
#     # heartbeat, irq and timers handle real work
#     time.sleep(1)
