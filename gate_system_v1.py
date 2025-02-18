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


class Gate:
    def __init__(self, motor_enable, motor_direction):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)

    def open_gate(self):
        self.motor_direction.value(1)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def close_gate(self):
        self.motor_direction.value(0)
        time.sleep(0.2)
        self.motor_enable.value(1)

    def stop_gate(self):
        self.motor_direction.value(0)
        time.sleep(0.2)
        self.motor_enable.value(0)


def close_gates():
    if pass_through_sensor.value():
        time.sleep(0.2)  # Debounce delay
        if pass_through_sensor.value():  # Confirm signal is still high
            open_gates()
            if close_gate_timer:
                close_gate_timer.deinit()
            close_gate_timer.init(
                period=GATE_OPEN_TIME * 1000, mode=Timer.ONE_SHOT, callback=close_gates
            )
            return

    if right_gate_close.value():
        right_gate.stop_gate()
    else:
        right_gate.close_gate()
        time.sleep(SWING_ARM_DELAY)

    if left_gate_close.value():
        left_gate.stop_gate()
    else:
        left_gate.close_gate()

    if close_gate_timer:
        close_gate_timer.deinit()


def open_gates():
    if left_gate_open.value():
        left_gate.stop_gate()
    else:
        left_gate.open_gate()
        time.sleep(SWING_ARM_DELAY)

    if right_gate_open.value():
        right_gate.stop_gate()
    else:
        right_gate.open_gate()


def stop_gate_callback(pin):
    if close_gate_timer:
        close_gate_timer.deinit()
    if left_gate_open.value() or right_gate_open.value():
        close_gate_timer.init(
            period=GATE_OPEN_TIME * 1000, mode=Timer.ONE_SHOT, callback=close_gates
        )
    if left_gate_close.value():
        left_gate.stop_gate()
    if right_gate_close.value():
        right_gate.stop_gate()


def pass_through_callback(pin):
    if close_gate_timer:
        close_gate_timer.deinit()
    close_gate_timer.init(
        period=GATE_OPEN_TIME * 1000, mode=Timer.ONE_SHOT, callback=close_gates
    )
    open_gates()


def front_desk_button_callback(pin):
    time.sleep(0.2)  # Debounce delay
    if pin.value():
        open_gates()


left_gate = Gate(K1_MOTOR_1, K2_MOTOR_1)
right_gate = Gate(K4_MOTOR_2, K3_MOTOR_2)

front_desk_button = Pin(OPEN_GATE_SWITCH, Pin.IN)
left_gate_open = Pin(LEFT_OPEN, Pin.IN)
left_gate_close = Pin(LEFT_CLOSE, Pin.IN)
right_gate_open = Pin(RIGHT_OPEN, Pin.IN)
right_gate_close = Pin(RIGHT_CLOSE, Pin.IN)
pass_through_sensor = Pin(PASS_THROUGH, Pin.IN)
close_gate_timer = Timer(0)

front_desk_button.irq(trigger=Pin.IRQ_RISING, handler=front_desk_button_callback)
left_gate_open.irq(trigger=Pin.IRQ_RISING, handler=stop_gate_callback)
right_gate_open.irq(trigger=Pin.IRQ_RISING, handler=stop_gate_callback)
right_gate_close.irq(trigger=Pin.IRQ_RISING, handler=stop_gate_callback)
left_gate_close.irq(trigger=Pin.IRQ_RISING, handler=stop_gate_callback)
pass_through_sensor.irq(trigger=Pin.IRQ_RISING, handler=pass_through_callback)

close_gates()
