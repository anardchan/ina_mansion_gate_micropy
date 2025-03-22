"""
This gate system app version is semi-timer based meaning, it is designed such that the gate will open and stop
based on the the sensor reading. For closing the gate, the stop will be based on the timer countdown.
"""

from machine import Pin, Timer  # type: ignore
import time

from gate_control import Gate

VERBOSE = True
verbose_print = print if VERBOSE else lambda *a, **k: None

##################
# PIN ASSIGNMENT #
##################

# Output pins
K1_MOTOR_1 = 16  # Pin that turns Motor 1 on/off
K2_MOTOR_1 = 17  # Pin that sets Motor 1 direction
K4_MOTOR_2 = 25  # Pin that turns Motor 2 on/off
K3_MOTOR_2 = 26  # Pin that sets Motor 2 direction
LAMP_PIN = 4  # Pin that turns the lamp on/off
# Input pins
GATE_1_OPEN_SENSOR_PIN = 36  # Pin that reads if gate 1 is fully open
GATE_2_OPEN_SENSOR_PIN = 39  # Pin that reads if gate 1 is fully closed
BREAK_SENSOR_PIN = 34  # Pin that detects if something passes through the gate
OPEN_GATE_SWITCH_PIN = 35  # Pin that opens the gate

################
# Timer Values #
################

KEEP_GATE_OPEN_TIME = 10000  # Default time to keep the gate open in ms
GATE_1_TIME_TO_CLOSE = 11500  # Default time to close gate 1 in ms
GATE_2_TIME_TO_CLOSE = 13000  # Default time to close gate 2 in ms
LAMP_PERIOD = 500  # Default time to blink the lamp in ms

##########################
# PIN Callback Functions #
##########################


def open_gate_switch_handler(pin):
    global system_active

    verbose_print("Button pressed.")
    if not system_active:
        system_active = True
        verbose_print("System activated.")
        # Enable IRQs
        gate_1_open_sensor.irq(
            trigger=Pin.IRQ_RISING, handler=gate_1_open_sensor_handler
        )
        verbose_print("Gate 1 opened sensor activated.")
        gate_2_open_sensor.irq(
            trigger=Pin.IRQ_RISING, handler=gate_2_open_sensor_handler
        )
        verbose_print("Gate 2 opened sensor activated.")
        break_sensor.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=break_sensor_handler
        )
        verbose_print("Break sensor activated.")

    gate_1_close_timer.deinit()
    verbose_print("Gate 1 close timer deactivated.")
    gate_2_close_timer.deinit()
    verbose_print("Gate 2 close timer deactivated.")

    if gate_1_open_sensor.value() == 0:  # If gate 1 is not fully open
        gate_1.move_ccw()  # Open gate 1
        lamp_timer.deinit()
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)
        verbose_print("Gate 1 will now be opened...")

    if gate_2_open_sensor.value() == 0:  # If gate 2 is not fully open
        gate_2.move_ccw()  # Open gate 2
        lamp_timer.deinit()
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)
        verbose_print("Gate 2 will now be opened...")

    # If gates are fully open, stop the motors and restart the timer
    if gate_1_open_sensor.value() == 1 or gate_2_open_sensor.value() == 1:
        gate_1.stop_gate()
        gate_2.stop_gate()
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        lamp_timer.deinit()
        lamp.value(1)
        verbose_print("Gates are fully opened. Restarting countdown timer...")


def gate_1_open_sensor_handler(pin):
    gate_1.stop_gate()
    verbose_print("Gate 1 opened.")
    gate_1_close_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    lamp_timer.deinit()
    lamp.value(1)
    verbose_print("Gate 1 is fully opened. Restarting countdown timer...")


def gate_2_open_sensor_handler(pin):
    gate_2.stop_gate()
    verbose_print("Gate 2 opened.")
    gate_2_close_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    lamp_timer.deinit()
    lamp.value(1)
    verbose_print("Gate 2 is fully opened. Restarting countdown timer...")


def break_sensor_handler(pin):
    if pin.value() == 1:
        verbose_print("Break sensor activated.")

        # If gates are fully open, stop the motors and restart the timer
        if gate_1_open_sensor.value() == 1 or gate_2_open_sensor.value() == 1:
            gate_1.stop_gate()
            gate_2.stop_gate()
            gate_countdown_timer.deinit()
            gate_countdown_timer.init(
                mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
            )
            lamp_timer.deinit()
            lamp.value(1)
            verbose_print("Gates are fully opened. Restarting countdown timer...")

        if gate_1_open_sensor.value() == 0:  # If gate 1 is not fully open
            gate_1.move_ccw()  # Open gate 1
            lamp_timer.deinit()
            lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)
            verbose_print("Gate 1 will now be opened...")

        if gate_2_open_sensor.value() == 0:  # If gate 2 is not fully open
            gate_2.move_ccw()  # Open gate 2
            lamp_timer.deinit()
            lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)
            verbose_print("Gate 2 will now be opened...")


############################
# TIMER callback functions #
############################


def close_gates(timer):
    if break_sensor.value() == 1:
        verbose_print("Attempted to close gates but break sensor is activated.")
        verbose_print("Restarting countdown timer...")
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        return

    gate_1.move_cw()
    verbose_print("Gate 1 will now be closed...")
    gate_1_close_timer.init(
        mode=Timer.ONE_SHOT, period=GATE_1_TIME_TO_CLOSE, callback=close_gate_1
    )
    time.sleep(1)
    gate_2.move_cw()
    verbose_print("Gate 2 will now be closed...")
    gate_2_close_timer.init(
        mode=Timer.ONE_SHOT, period=GATE_2_TIME_TO_CLOSE, callback=close_gate_2
    )
    lamp_timer.deinit()
    lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)


def close_gate_1(timer):
    gate_1.stop_gate()
    # No need to stop the lamp blinking
    verbose_print("Gate 1 closed.")


def close_gate_2(timer):
    gate_2.stop_gate()
    # No need to stop the lamp blinking, handled in deactivate_system()
    verbose_print("Gate 2 closed.")
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

    # Disable IRQs
    gate_1_open_sensor.irq(trigger=0, handler=None)
    gate_2_open_sensor.irq(trigger=0, handler=None)
    break_sensor.irq(trigger=0, handler=None)

    gate_countdown_timer.deinit()
    gate_1_close_timer.deinit()
    gate_2_close_timer.deinit()

    lamp_timer.deinit()
    lamp.value(1)
    time.sleep(3)
    lamp.value(0)


system_active = False

gate_1 = Gate(K1_MOTOR_1, K2_MOTOR_1)
gate_2 = Gate(K4_MOTOR_2, K3_MOTOR_2)
lamp = Pin(LAMP_PIN, Pin.OUT)

gate_1_open_sensor = Pin(GATE_1_OPEN_SENSOR_PIN, Pin.IN)
gate_2_open_sensor = Pin(GATE_2_OPEN_SENSOR_PIN, Pin.IN)
break_sensor = Pin(BREAK_SENSOR_PIN, Pin.IN)
open_gate_switch = Pin(OPEN_GATE_SWITCH_PIN, Pin.IN)

gate_countdown_timer = Timer(0)
gate_1_close_timer = Timer(1)
gate_2_close_timer = Timer(2)
lamp_timer = Timer(3)

open_gate_switch.irq(trigger=Pin.IRQ_RISING, handler=open_gate_switch_handler)
