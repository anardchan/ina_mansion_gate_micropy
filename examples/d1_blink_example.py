# Import necessary modules
from machine import Pin  # type: ignore # Import Pin class from machine module to control GPIO pins
import time  # Import time module for delay functions

# Initialize the LED pin
led_pin = Pin(2, Pin.OUT)  # Create a Pin object for GPIO2 and set it as an output pin

# Main loop to blink the LED
while True:
    led_pin.on()  # Turn the LED on
    time.sleep(1)  # Wait for 1 second
    led_pin.off()  # Turn the LED off
    time.sleep(1)  # Wait for 1 second