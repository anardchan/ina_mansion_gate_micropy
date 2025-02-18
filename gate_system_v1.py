from machine import Pin, Timer  # type: ignore
import time

# Define the pins numbers
K1_MOTOR_1 = 1  # Pin that turns Motor 1 on/off
K2_MOTOR_1 = 2  # Pin that sets Motor 1 direction
K4_MOTOR_2 = 3  # Pin that turns Motor 2 on/off
K3_MOTOR_2 = 4  # Pin that sets Motor 2 direction

# Pins that are interrupt signals
RIGHT_OPEN = 5  # Pin that detects if the right gate is open
RIGHT_CLOSE = 6  # Pin that detects if the right gate is closed
LEFT_OPEN = 7  # Pin that detects if the left gate is open
LEFT_CLOSE = 8  # Pin that detects if the left gate is closed
PASS_THROUGH = 9  # Pin that detects if a vehicle is passing through the gate
OPEN_GATE_SWITCH = 10  # Pin that opens the gate and starts the system

# Defines
GATE_OPEN_TIME = 10  # Default time to keep the gate open
SWING_ARM_DELAY = 1.2  # Reduced delay before the other gate moves

# System Variables
system_active = False


class Gate:
    def __init__(self, motor_enable, motor_direction, open_sensor, close_sensor):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)
        self.open_sensor = Pin(open_sensor, Pin.IN)
        self.close_sensor = Pin(close_sensor, Pin.IN)

    def is_opened(self):
        """
        Non-blocking function reads if the gate is fully opened.
        """
        return self.open_sensor.value()

    def is_closed(self):
        """
        Non-blocking function reads if the gate is fully closed.
        """
        return self.close_sensor.value()

    def start_opening_gate(self):
        """
        Non-blocking function that starts opening the gate.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(1)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def start_closing_gate(self):
        """
        Non-blocking function that starts closing the gate.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(0)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def try_opening_gate(self):
        if self.is_opened():
            self.stop_gate()
        else:
            self.start_opening_gate()

    def try_closing_gate(self):
        if self.is_closed():
            self.stop_gate()
        else:
            self.start_closing_gate()

    def stop_gate(self):
        """
        Non-blocking function that stops.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(0)


right_gate = Gate(K1_MOTOR_1, K2_MOTOR_1, RIGHT_OPEN, RIGHT_CLOSE)
left_gate = Gate(K4_MOTOR_2, K3_MOTOR_2, LEFT_OPEN, LEFT_CLOSE)

pass_through_sensor = Pin(PASS_THROUGH, Pin.IN)
open_gate_switch = Pin(OPEN_GATE_SWITCH, Pin.IN)


def start_system():
    global system_active
    right_gate.try_opening_gate()
    time.sleep(1.5)
    left_gate.try_opening_gate()

    while right_gate.is_opened() is not True:
        time.sleep(0.1)
    right_gate.stop_gate()

    while left_gate.is_opened() is not True:
        time.sleep(0.1)
    left_gate.stop_gate()

    start_time = time.time()
    while time.time < start_time + 10:
        if pass_through_sensor.value() == 1:
            start_time = time.time()

    right_gate.try_closing_gate()
    time.sleep(1.5)
    left_gate.try_closing_gate()

    while right_gate.is_closed() is not True:
        time.sleep(0.1)
        if pass_through_sensor.value() == 1 or open_gate_switch.value() == 1:
            start_system()
            system_active = False
            return
    right_gate.stop_gate()

    while left_gate.is_closed() is not True:
        time.sleep(0.1)
    left_gate.stop_gate()

    system_active = False


def open_gate_switch_handler(pin):
    global system_active
    if system_active:
        pass
    else:
        system_active = True
        start_system()


open_gate_switch.irq(trigger=Pin.IRQ_RISING, handler=open_gate_switch_handler)
