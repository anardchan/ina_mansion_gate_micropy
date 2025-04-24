# \xc8\x2e\x18\x51\x7e\xe9 sender
# \xc8\x2e\x18\x51\xc8\x5c receiver

import network  # type: ignore
import espnow  # type: ignore
import time

from machine import Pin # type: ignore


class PinDebounce:
    """
    A class that implements a debounced switch using an external pull-up resistor.

    Attributes:
        pin (Pin): GPIO pin for the switch input.
        callback (function): Function to execute on a valid press.
        debounce_time (int): Debounce time in milliseconds.
        last_press_time (int): Stores the last valid press timestamp.
    """

    def __init__(self, pin_number, callback, debounce_time=50):
        """
        Initializes the debounced switch.

        Args:
            pin_number (int): The GPIO pin number to which the switch is connected.
            callback (function): Function to call when the switch is pressed.
            debounce_time (int): Minimum time between valid presses (in ms).
        """
        self.pin = Pin(pin_number, Pin.IN)  # Using external pull-down
        self.callback = callback
        self.debounce_time = debounce_time
        self.last_press_time = 0  # Store last press time
        self.irq_handler = self._irq_handler  # Store the IRQ handler function
        self.disable_irq()  # Disable IRQ on initialization

    def _irq_handler(self, pin):
        """
        Interrupt handler for switch press events.

        Args:
            pin (Pin): The GPIO pin instance that triggered the interrupt.
        """
        time.sleep_ms(5)  # Small delay for stability
        if pin.value() == 1:  # Ensure it's still HIGH (pressed)
            current_time = time.ticks_ms()
            if time.ticks_diff(current_time, self.last_press_time) > self.debounce_time:
                self.last_press_time = current_time
                self.callback()  # Execute the user-defined function

    def disable_irq(self):
        """
        Disables the IRQ for the switch to prevent further interrupts.
        """
        self.pin.irq(trigger=0, handler=None)  # Disable IRQ

    def enable_irq(self):
        """
        Enables the IRQ for the switch to detect button presses again.
        """
        self.pin.irq(trigger=Pin.IRQ_RISING, handler=self.irq_handler)  # Enable IRQ


# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.STA_IF)  # Or network.AP_IF
sta.active(True)
sta.disconnect()  # For ESP8266

e = espnow.ESPNow()
e.active(True)
peer = b"\xc8\x2e\x18\x51\xc8\x5c"  # MAC address of peer's wifi interface
e.add_peer(peer)  # Must add_peer() before send()

# e.send(peer, "Starting...")
# for i in range(100):
#     e.send(peer, str(i) * 20, True)
# e.send(peer, b"\x01")


def pb_cb():
    print("Button pressed")
    e.send(peer, b"\x01")


debounced_switch = PinDebounce(pin_number=36, callback=pb_cb, debounce_time=100)
debounced_switch.enable_irq()  # Enable IRQ for the switch