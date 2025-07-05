"""
espnow_handler.py

Handles ESP-NOW peer communication setup and message dispatching
for the ESP32 boards in the gate access control system.

Author: Allan Bernard Chan
Date: July 2025
"""

import espnow  # type: ignore
import network  # type: ignore
import time

class ESPNowHandler:
    """
    A class to manage ESP-NOW peer-to-peer messaging.

    Attributes:
        peers (dict): Dictionary of known peer MACs and their roles.
    """
    def __init__(self, wifi_interface=None):
        """
        Initializes ESP-NOW and Wi-Fi interface.

        Args:
            wifi_interface: Optional network interface to use.
        """
        self.iface = wifi_interface or network.WLAN(network.STA_IF)
        self.iface.active(True)
        self.iface.disconnect()  # Ensure no active connections

        self.espnow = espnow.ESPNow()
        self.espnow.active(True)

        self.peers = []

    def add_peer(self, mac):
        """
        Adds a peer to the ESP-NOW peer list.

        Args:
            mac (bytes): MAC address of the peer.
        """
        if mac not in self.peers:
            self.espnow.add_peer(mac)
            self.peers.append(mac)

    def send(self, mac, msg):
        """
        Sends a message to a specified peer.

        Args:
            mac (bytes): MAC address of the peer.
            msg (bytes): Message payload to send.
        """
        try:
            self.espnow.send(mac, msg)
        except Exception as e:
            print(f"[ESPNow] Failed to send to {mac}: {e}")

    def recv(self, timeout_ms=5000):
        """
        Waits for a message to be received.

        Args:
            timeout_ms (int): Timeout in milliseconds.
        Returns:
            (mac, msg): Tuple of sender MAC and message payload or (None, None) if timeout.
        """
        # start = time.ticks_ms()
        # while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        #     if self.espnow.poll():
        #         mac, msg = self.espnow.recv()
        #         return mac, msg
        # return None, None
        try:
            mac, msg = self.espnow.irecv(timeout_ms)
        except OSError as e:
            print(f"[ESPNow] Error receiving message: {e}")
            return None, None
        except Exception as e:
            print(f"[ESPNow] Unexpected error: {e}")
            return None, None
        else:
            return mac, msg
