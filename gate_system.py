"""
This gate system app version is semi-timer based meaning, it is designed such that the gate will open and stop
based on the the sensor reading. For closing the gate, the stop will be based on the timer countdown.
"""

from machine import Pin, Timer  # type: ignore
import time

from lib.gate_control import Gate
from lib.bounce import PinDebounce

VERBOSE = True
verbose_print = print if VERBOSE else lambda *a, **k: None

##################
# PIN ASSIGNMENT #
##################

# Output pins
K1_MOTOR_1 = 33  # Pin that turns Motor 1 on/off
K2_MOTOR_1 = 25  # Pin that sets Motor 1 direction
K4_MOTOR_2 = 26  # Pin that turns Motor 2 on/off
K3_MOTOR_2 = 27  # Pin that sets Motor 2 direction
LAMP_PIN = 32  # Pin that turns the lamp on/off
# Input pins
GATE_1_OPEN_SENSOR_PIN = 36  # Pin that reads if gate 1 is fully open
GATE_2_OPEN_SENSOR_PIN = 39  # Pin that reads if gate 1 is fully closed
BREAK_SENSOR_PIN = 34  # Pin that detects if something passes through the gate
OPEN_GATE_SWITCH_PIN = 35  # Pin that opens the gate
# RC522 pins
# RC522_RST_PIN = 16 # Pin reset or power down the module
# RC522_IRQ_PIN = 17 # Pin that reads the interrupt request
# RC522_MISO_PIN = 12 # Pin for MISO
# RC522_MOSI_PIN = 13 # Pin for MOSI
# RC522_SCK_PIN = 14 # Pin for SCK
# RC522_SS_GATE_IN_PIN = 15  # Pin for SS

################
# Timer Values #
################

KEEP_GATE_OPEN_TIME = 10000  # Default time to keep the gate open in ms
GATE_1_TIME_TO_CLOSE = 11000  # Default time to close gate 1 in ms
GATE_2_TIME_TO_CLOSE = 12280  # Default time to close gate 2 in ms
LAMP_PERIOD = 400  # Default time to blink the lamp in ms

#############
# Variables #
#############

system_active = False
gate_1_status = 0  # 0 = closed, 1 = not closed
gate_2_status = 0  # 0 = closed, 1 = not closed

##########################
# PIN Callback Functions #
##########################


def open_gate_switch_handler():
    global system_active
    global gate_1_status
    global gate_2_status
    verbose_print("Button pressed.")
    if not system_active:
        system_active = True
        verbose_print("System activated.")
        # Enable IRQs
        break_sensor.enable_irq()
        verbose_print("Break sensor interrupt service activated.")

    gate_1_close_timer.deinit()
    verbose_print("Gate 1 close timer deactivated.")
    gate_2_close_timer.deinit()
    verbose_print("Gate 2 close timer deactivated.")

    if gate_1_open_sensor.pin.value() == 1:
        gate_1.stop_gate()  # Stop gate 1 motor
        verbose_print("Gate 1 opened fully opened.")
        gate_1_open_sensor.disable_irq()  # Disable gate 1 open sensor interrupt service
        verbose_print(
            "Gate 1 opened sensor interrupt service deactivated - reached open sensor."
        )
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        lamp_timer.deinit()
        lamp.value(1)

    if gate_2_open_sensor.pin.value() == 1:
        gate_2.stop_gate()  # Stop gate 2 motor
        verbose_print("Gate 2 opened fully opened.")
        gate_2_open_sensor.disable_irq()  # Disable gate 2 open sensor interrupt service
        verbose_print(
            "Gate 2 opened sensor interrupt service deactivated - reached open sensor."
        )
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        lamp_timer.deinit()
        lamp.value(1)

    if gate_1_open_sensor.pin.value() == 0:  # If gate 1 is not fully open
        gate_1_open_sensor.enable_irq()  # Enable gate 1 open sensor interrupt service
        verbose_print(
            "Gate 1 opened sensor interrupt service activated. - push button pressed"
        )
        gate_1.move_ccw()  # Open gate 1
        verbose_print("Gate 1 will now be opened (by push button)...")
        gate_1_status = 1  # Set gate 1 status to not closed
        lamp_timer.deinit()
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)

    if gate_2_open_sensor.pin.value() == 0:  # If gate 2 is not fully open
        gate_2_open_sensor.enable_irq()  # Enable gate 2 open sensor interrupt service
        verbose_print(
            "Gate 2 opened sensor interrupt service activated. - push button pressed"
        )
        gate_2.move_ccw()  # Open gate 2
        verbose_print("Gate 2 will now be opened (by push button)...")
        gate_2_status = 1  # Set gate 2 status to not closed
        lamp_timer.deinit()
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)


def gate_1_open_sensor_handler():
    time.sleep(1)
    gate_1.stop_gate()  # Stop gate 1 motor
    verbose_print("Gate 1 opened.")
    gate_1_open_sensor.disable_irq()  # Disable gate 1 open sensor interrupt service
    verbose_print(
        "Gate 1 opened sensor interrupt service deactivated - reached open sensor."
    )
    gate_1_close_timer.deinit()
    gate_countdown_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    verbose_print("Gate 1 is fully opened. Restarting countdown timer...")
    lamp_timer.deinit()
    lamp.value(1)


def gate_2_open_sensor_handler():
    time.sleep(1)
    gate_2.stop_gate()  # Stop gate 2 motor
    verbose_print("Gate 2 opened.")
    gate_2_open_sensor.disable_irq()  # Disable gate 2 open sensor interrupt service
    verbose_print(
        "Gate 2 opened sensor interrupt service deactivated - reached open sensor."
    )
    gate_2_close_timer.deinit()
    gate_countdown_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    lamp_timer.deinit()
    lamp.value(1)
    verbose_print("Gate 2 is fully opened. Restarting countdown timer...")


def break_sensor_handler():
    if break_sensor.pin.value() == 1:
        verbose_print("Break sensor activated.")

        if gate_1_open_sensor.pin.value() == 1:
            gate_1.stop_gate()  # Stop gate 1 motor
            verbose_print("Gate 1 opened fully opened.")
            gate_1_open_sensor.disable_irq()  # Disable gate 1 open sensor interrupt service
            verbose_print(
                "Gate 1 opened sensor interrupt service deactivated - reached open sensor."
            )
            gate_countdown_timer.deinit()
            gate_countdown_timer.init(
                mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
            )
            lamp_timer.deinit()
            lamp.value(1)

        if gate_2_open_sensor.pin.value() == 1:
            gate_2.stop_gate()  # Stop gate 2 motor
            verbose_print("Gate 2 opened fully opened.")
            gate_2_open_sensor.disable_irq()  # Disable gate 2 open sensor interrupt service
            verbose_print(
                "Gate 2 opened sensor interrupt service deactivated - reached open sensor."
            )
            gate_countdown_timer.deinit()
            gate_countdown_timer.init(
                mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
            )
            lamp_timer.deinit()
            lamp.value(1)

        if gate_1_open_sensor.pin.value() == 0:  # If gate 1 is not fully open
            gate_1.move_ccw()  # Open gate 1
            verbose_print("Gate 1 will now be opened...")
            gate_1_open_sensor.enable_irq()  # Enable gate 1 open sensor interrupt service
            verbose_print(
                "Gate 1 opened sensor interrupt service activated by break sensor."
            )
            lamp_timer.deinit()
            lamp_timer.init(
                mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink
            )

        if gate_2_open_sensor.pin.value() == 0:  # If gate 2 is not fully open
            gate_2.move_ccw()  # Open gate 2
            verbose_print("Gate 2 will now be opened...")
            gate_2_open_sensor.enable_irq()  # Enable gate 2 open sensor interrupt service
            verbose_print(
                "Gate 2 opened sensor interrupt service activated by break sensor."
            )
            lamp_timer.deinit()
            lamp_timer.init(
                mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink
            )


############################
# TIMER callback functions #
############################


def close_gates(timer):
    global gate_1_status
    global gate_2_status
    if break_sensor.pin.value() == 1:
        verbose_print("Attempted to close gates but break sensor is activated.")
        verbose_print("Restarting countdown timer...")
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        return
    if gate_1_status == 1:  # If gate 1 is not closed
        verbose_print("Gate 1 will now be closed...")
        gate_1.move_cw()
        gate_1_close_timer.init(
            mode=Timer.ONE_SHOT, period=GATE_1_TIME_TO_CLOSE, callback=close_gate_1
        )
    time.sleep(1)
    if gate_2_status == 1:  # If gate 2 is not closed
        verbose_print("Gate 2 will now be closed...")
        gate_2.move_cw()
        gate_2_close_timer.init(
            mode=Timer.ONE_SHOT, period=GATE_2_TIME_TO_CLOSE, callback=close_gate_2
        )
    lamp_timer.deinit()
    lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)


def close_gate_1(timer):
    global gate_1_status
    gate_1.stop_gate()
    # No need to stop the lamp blinking
    verbose_print("Gate 1 closed.")
    gate_1_status = 0  # Set gate 1 status to closed


def close_gate_2(timer):
    global gate_2_status
    gate_2.stop_gate()
    # No need to stop the lamp blinking, handled in deactivate_system()
    verbose_print("Gate 2 closed.")
    gate_2_status = 0  # Set gate 2 status to closed
    deactivate_system()
    print("System deactivated.")


def lamp_blink(timer):
    lamp.value(not lamp.value())


####################
# Global Functions #
####################


def deactivate_system():
    global system_active
    system_active = False
    verbose_print("Deactivating system...")

    # Disable IRQs
    gate_1_open_sensor.disable_irq()
    gate_2_open_sensor.disable_irq()
    break_sensor.disable_irq()

    gate_countdown_timer.deinit()
    gate_1_close_timer.deinit()
    gate_2_close_timer.deinit()

    lamp_timer.deinit()
    lamp.value(0)


gate_1 = Gate(K1_MOTOR_1, K2_MOTOR_1)
gate_2 = Gate(K4_MOTOR_2, K3_MOTOR_2)
lamp = Pin(LAMP_PIN, Pin.OUT)

gate_1_open_sensor = PinDebounce(
    GATE_1_OPEN_SENSOR_PIN, gate_1_open_sensor_handler, debounce_time=3000
)
gate_2_open_sensor = PinDebounce(
    GATE_2_OPEN_SENSOR_PIN, gate_2_open_sensor_handler, debounce_time=3000
)
break_sensor = PinDebounce(BREAK_SENSOR_PIN, break_sensor_handler, debounce_time=500)
open_gate_switch = PinDebounce(
    OPEN_GATE_SWITCH_PIN, open_gate_switch_handler, debounce_time=500
)

gate_countdown_timer = Timer(0)
gate_1_close_timer = Timer(1)
gate_2_close_timer = Timer(2)
lamp_timer = Timer(3)

open_gate_switch.enable_irq()
