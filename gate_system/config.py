# MACS
ADMIN_MAC = b"\x1c\x69\x20\xce\xf8\xe4"
GATE_GUARD_MAC = b'\x1c\x69\x20\xce\xfa\x24'
INSIDE_READER_MAC = b"\x08\xa6\xf7\xbc\xe5\x48"
BENINCA_HEAD_MAC = b'\xc8\x2e\x18\x51\xc8\x5c'
BACKUP_BUTTON_MAC = b'\x1c\x69\x20\xce\xf7\xe4'
OUTSIDE_READER_MAC = b"\x1c\x69\x20\xcc\xe0\x34"

READER_MACS = {
    INSIDE_READER_MAC,
    OUTSIDE_READER_MAC
}
TEST_BOARD_MAC = b"\xc8\x2e\x18\x51\x7e\xe8"

# Card Types
class CardType:
    NONE = 0
    MONTHLY = 1
    DAILY = 2
    SINGLE_ENTRY = 3

# Pricing
MONTHLY_RATE_PHP = 5000
DAILY_RATE_PHP = 50
SINGLE_ENTRY_RATE_FIRST_HOURS = 40
SINGLE_ENTRY_FIRST_HOURS_DURATION = 4
SINGLE_ENTRY_EXTRA_HOUR_RATE = 10
GRACE_MINS = 1

# NTP
NTP_SERVERS = ["3.pool.ntp.org", "time.nist.gov", "0.asia.pool.ntp.org", "1.asia.pool.ntp.org", "pool.ntp.org", "asia.pool.ntp.org", "europe.pool.ntp.org", "america.pool.ntp.org", "ntp.pagasa.dost.gov.ph", "time.upd.edu.ph", "us.pool.ntp.org"]
UTC_OFFSET = 8 * 60 * 60  # GMT+8

# Log settings
LOG_DIR = "logs"
LOG_FILE_PREFIX = "log_"
LOG_MAX_FILES = 8  # 2 months * 4 weeks
MAX_LOG_LINES = 500  # configurable

# Wi-Fi Credentials
SSID = "Converge_2.4GHz_3Fck" 
SSID_PW = "6tYjdM8m" 