import time
from machine import Pin  # type: ignore


class Gate:
    def __init__(self, motor_enable, motor_direction):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)

    def move_ccw(self):
        """
        Non-blocking function that moves the gate one way.
        """
        self.motor_enable.value(0)
        time.sleep(0.1)
        self.motor_direction.value(1)
        time.sleep(0.1)
        self.motor_enable.value(1)

    def move_cw(self):
        """
        Non-blocking function that starts closing the gate.
        """
        self.motor_enable.value(0)
        time.sleep(0.1)
        self.motor_direction.value(0)
        time.sleep(0.1)
        self.motor_enable.value(1)

    def stop_gate(self):
        """
        Non-blocking function that stops.
        """
        self.motor_enable.value(0)
        time.sleep(0.1)
        self.motor_direction.value(0)
