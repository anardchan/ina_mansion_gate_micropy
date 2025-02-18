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
SWING_ARM_DELAY = 1.5  # Delay before the other gate moves

class SwingArmController:
    def __init__(
        self, motor_enable, motor_direction, open_sensor, close_sensor, delay=1.5
    ):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)
        self.open_sensor = Pin(open_sensor, Pin.IN)
        self.close_sensor = Pin(close_sensor, Pin.IN)
        self.delay = delay  # Delay before the other gate moves

    def is_open(self):
        return self.open_sensor.value() == 1

    def is_closed(self):
        return self.close_sensor.value() == 1

    def open_gate(self):
        if self.is_open() is not True:
            self.motor_direction.value(1)  # Set direction to open
            self.motor_enable.value(1)  # Start motor

    def close_gate(self):
        if not self.is_closed():
            self.motor_direction.value(0)  # Set direction to close
            self.motor_enable.value(1)  # Start motor

    def stop_gate(self):
        self.motor_direction.value(0)  # Just don't provide a signal to the relay
        self.motor_enable.value(0)  # Stop motor


class GateSystem:
    def __init__(self):
        self.left_gate = SwingArmController(
            K1_MOTOR_1, K2_MOTOR_1, LEFT_OPEN, LEFT_CLOSE
        )
        self.right_gate = SwingArmController(
            K4_MOTOR_2, K3_MOTOR_2, RIGHT_OPEN, RIGHT_CLOSE
        )
        self.pass_through = Pin(PASS_THROUGH, Pin.IN)
        self.open_gate_switch = Pin(
            OPEN_GATE_SWITCH, Pin.IN, Pin.IRQ_FALLING, self.start_system
        )
        self.timer = Timer(-1)
        self.gate_open_time = GATE_OPEN_TIME
        self.gate_closing = False
        self.check_gate_status_on_boot()

    def check_gate_status_on_boot(self):
        if (
            self.left_gate.is_open() is not True
            or self.right_gate.is_open() is not True
        ):
            self.close_gates()

    def start_system(self, pin):
        if self.gate_closing is not True:
            self.open_gates()

    def open_gates(self):
        """
        Blocking method that waits for gates to open and manages them accordingly.
        """
        self.left_gate.open_gate()
        time.sleep(self.left_gate.delay)
        self.right_gate.open_gate()
        self.monitor_gates(self.left_gate, self.right_gate)
        self.keep_gate_open()

    def monitor_gates(self, gate1, gate2):
        """
        Blocking method that waits for the gates to be fully open or closed.
        """
        while gate1.is_open() is not True or gate1.is_closed() is not True:
            time.sleep(0.1)
        gate1.stop_gate()
        while gate2.is_open() is not True or gate2.is_closed() is not True:
            time.sleep(0.1)
        gate2.stop_gate()

    def keep_gate_open(self):
        """
        Blocking method that keeps the gate open for a specified time.
        The specified time is reset when a vehicle passes through the gate.
        """
        start_time = time.time()
        while time.time() - start_time < self.gate_open_time:
            if self.pass_through.value() == 1:
                start_time = time.time()
            time.sleep(0.1)
        self.close_gates()

    def close_gates(self):
        self.gate_closing = True
        self.right_gate.close_gate()
        time.sleep(self.right_gate.delay)
        self.left_gate.close_gate()

        while not (self.right_gate.is_closed() or self.left_gate.is_closed()):
            if self.pass_through.value() == 1:  # Safety feature: reopen if interrupted
                self.open_gates()
                return
            if (
                self.open_gate_switch.value() == 1
            ):  # Safety feature: reopen if interrupted
                self.open_gates()
                return
            time.sleep(0.1)

        self.monitor_gates(self.right_gate, self.left_gate)
        self.gate_closing = False


system = GateSystem()
while True:
    time.sleep(1)  # Keep the script running
