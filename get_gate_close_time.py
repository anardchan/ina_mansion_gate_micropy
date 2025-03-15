from machine import Pin  # type: ignore
import time

# Define the pins numbers
# K1_MOTOR_1 = 1  # Pin that turns Motor 1 on/off
# K2_MOTOR_1 = 2  # Pin that sets Motor 1 direction
# K4_MOTOR_2 = 3  # Pin that turns Motor 2 on/off
# K3_MOTOR_2 = 4  # Pin that sets Motor 2 direction
KX_MOTOR_EN = 16  # Pin that turns Motor on/off
KX_MOTOR_DIR = 17  # Pin that sets Motor direction
STATUS_LED_PIN = 4  # Pin that indicates if main is running

DIRECTION_PIN = 36  # Pin that dictates the direction of the motor
START_PIN = 39  # Pin that starts the motor movement
STOP_PIN = 34  # Pin that stops the motor movement


class Gate:
    def __init__(self, motor_enable, motor_direction):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)

    def move_ccw(self):
        """
        Non-blocking function that moves the gate one way.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(1)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def move_cw(self):
        """
        Non-blocking function that starts closing the gate.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(0)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def stop_gate(self):
        """
        Non-blocking function that stops.
        """
        self.motor_enable.value(0)
        time.sleep(0.2)
        self.motor_direction.value(0)


def main_boot_display():
    print("Gate System v1.0")
    print("Starting system...")
    main_status = Pin(STATUS_LED_PIN, Pin.OUT)  # Status LED
    main_status.value(1)
    time.sleep(1)
    main_status.value(0)
    time.sleep(1)
    main_status.value(1)
    print("System started.")


def direction_callback(pin):
    global start_time
    global end_time
    global direction_value
    if direction.value() == 0:
        direction_value = 0
    else:
        direction_value = 1

    print(f"Direction value: {direction_value}")


def start_callback(pin):
    global start_time
    global end_time
    global direction_value
    if start.value() == 1:
        print("Starting motor movement... ")
        print(f"Direction value: {direction_value}")
        if direction_value == 0:
            print(f"Moving in direction {direction_value}")
            start_time = time.ticks_ms()
            gate_x.move_cw()
        else:
            print(f"Moving in direction {direction_value}")
            start_time = time.ticks_ms()
            gate_x.move_ccw()


def stop_callback(pin):
    global start_time
    global end_time
    global direction_value
    if stop.value() == 1:
        print("Stopping motor movement...")
        end_time = time.ticks_ms()
        gate_x.stop_gate()
        print("Gate closed.")
        print("Time taken to close the gate: ", end_time - start_time, "ms")


gate_x = Gate(KX_MOTOR_EN, KX_MOTOR_DIR)

direction = Pin(DIRECTION_PIN, Pin.IN)
start = Pin(START_PIN, Pin.IN)
stop = Pin(STOP_PIN, Pin.IN)

direction_value = 0

start_time = 0
end_time = 0

main_boot_display()

direction.irq(
    trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
    handler=direction_callback,
)

start.irq(
    trigger=Pin.IRQ_RISING,
    handler=start_callback,
)

stop.irq(
    trigger=Pin.IRQ_RISING,
    handler=stop_callback,
)
