"""
MicroPython Switch Debounce Using time.ticks_ms()

This module implements a debounced switch input using an IRQ pin without using a Timer.
The debounce logic is handled via a time-based approach, ensuring stable switch presses.

Author: Allan Bernard Chan
Date: March 2025
"""

from machine import Pin  # type: ignore
import time


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
        self.pin = Pin(pin_number, Pin.IN)  # Using external pull-up
        self.callback = callback
        self.debounce_time = debounce_time
        self.last_press_time = 0  # Store last press time
        self.pin.irq(
            trigger=Pin.IRQ_FALLING, handler=self._irq_handler
        )  # Detect falling edge

    def _irq_handler(self, pin):
        """
        Interrupt handler for switch press events.

        Args:
            pin (Pin): The GPIO pin instance that triggered the interrupt.
        """
        time.sleep_ms(5)  # Small delay for stability
        if pin.value() == 0:  # Ensure it's still LOW (pressed)
            current_time = time.ticks_ms()
            if time.ticks_diff(current_time, self.last_press_time) > self.debounce_time:
                self.last_press_time = current_time
                self.callback()  # Execute the user-defined function


if __name__ == "__main__":

    def switch_pressed():
        """
        Callback function that runs when the switch is successfully pressed (debounced).
        """
        print("Switch pressed!")

    # Initialize the debounced switch on GPIO 15 with a debounce time of 50ms
    debounced_switch = PinDebounce(
        pin_number=36, callback=switch_pressed, debounce_time=100
    )
