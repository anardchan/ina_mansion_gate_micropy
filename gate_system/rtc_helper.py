"""
RTC Helper Module
-----------------
Handles NTP time synchronization and UTC offset adjustment.
"""

import time
import ntptime # type: ignore
import network # type: ignore
from config import SSID, PW, NTP_SERVERS, UTC_OFFSET   

def sync_time():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if not sta.isconnected():
        print("Connecting to WiFi...")
        sta.connect(f"{SSID}", f"{PW}")  # Fill these with your AP values
        while not sta.isconnected():
            pass
    print('Connection successful')
    print(sta.ifconfig()[0])  # Print the IP address
    
    ntptime.host = NTP_SERVERS[0] # Set NTP server
    ntptime.timeout = 1  # Set timeout for NTP request
    ntptime.settime()  # Synchronize time with NTP server

def get_local_time_s():
    return time.time() + UTC_OFFSET  # Get local time in seconds since epoch adjusted for UTC offset

def get_local_time():
    return time.localtime(time.time() + UTC_OFFSET)
