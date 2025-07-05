"""
This gate system app version is semi-timer based meaning, it is designed such that the gate will open and stop
based on the the sensor reading. For closing the gate, the stop will be based on the timer countdown.
"""

import network  # type: ignore
import espnow  # type: ignore

from lib.gate_control import Gate
from lib.bounce import PinDebounce

from machine import Pin, Timer  # type: ignore

VERBOSE = True
verbose_print = print if VERBOSE else lambda *a, **k: None

##################
# PIN ASSIGNMENT #
##################

# Output pins
LAMP_PIN = 32  # Pin that turns the lamp on/off
K1_MOTOR_1 = 33  # Pin that turns Motor 1 on/off
K2_MOTOR_1 = 25  # Pin that sets Motor 1 direction
K4_MOTOR_2 = 26  # Pin that turns Motor 2 on/off
K3_MOTOR_2 = 27  # Pin that sets Motor 2 direction
# Input pins
GATE_1_OPEN_SENSOR_PIN = 36  # Pin that reads if gate 1 is fully open
GATE_2_OPEN_SENSOR_PIN = 39  # Pin that reads if gate 1 is fully closed
BREAK_SENSOR_PIN = 34  # Pin that detects if something passes through the gate
OPEN_GATE_SWITCH_PIN = 35  # Pin that opens the gate

################
# Timer Values #
################

KEEP_GATE_OPEN_TIME = 15000  # Default time to keep the gate open in ms
GATE_1_TIME_TO_CLOSE = 11000  # Default time to close gate 1 in ms
GATE_2_TIME_TO_CLOSE = 12300  # Default time to close gate 2 in ms
LAMP_PERIOD = 500  # Default time to blink the lamp in ms

#############
# Variables #
#############

system_active = False

##########################
# PIN Callback Functions #
##########################


def open_gate_switch_handler():
    global system_active

    verbose_print("Button pressed.")
    # If system is inactive, activate it
    if not system_active:
        system_active = True
        verbose_print("System activated.")

    gate_1_close_timer.deinit()
    verbose_print("Gate 1 close timer deactivated.")
    gate_2_close_timer.deinit()
    verbose_print("Gate 2 close timer deactivated.")

    if gate_1.status == 0:  # # If gate 1 is closed and PB is pressed.
        gate_1.move_ccw()  # Open gate 1
        verbose_print("Gate 1 will now be opened...")
        gate_1_open_sensor.enable_irq()
        verbose_print(
            "Gate 1 opened sensor interrupt service activated - push button pressed"
        )
        verbose_print("Lamp blinking started by gate 1 - PB.")
        gate_1.status = 1  # Set gate 1 status to opening.
        break_sensor.disable_irq()  # Disable break sensor interrupt service
    elif gate_1.status == 1:  # If gate 1 is opening and PB is pressed.
        verbose_print("Gate 1 is already opening...")
        verbose_print("PB did not affect the gate 1 motor.")
    elif gate_1.status == 2:  # If gate 1 is opened and PB is pressed.
        verbose_print("Gate 1 is already opened...")
        verbose_print("PB restarting the countdown timer.")
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        verbose_print("PB has restarted the countdown timer.")
    elif gate_1.status == 3:  # If gate 1 is closing and PB is pressed.
        gate_1_close_timer.deinit()  # Deactivate the timer
        gate_1.stop_gate()  # Stop gate 1 motor
        if gate_1_open_sensor.pin.value() == 0:
            gate_1.move_ccw()  # Open gate 1
            verbose_print("Gate 1 will now be opened...")
            gate_1_open_sensor.enable_irq()
            gate_1.status = 1  # Set gate 1 status to opening.
        else:
            gate_1.status = 2  # Set gate 1 status to opened
    else:
        verbose_print("Gate 1 is in an unknown state...")

    if gate_2.status == 0:  # If gate 2 is closed and PB is pressed.
        gate_2.move_ccw()  # Open gate 2
        verbose_print("Gate 2 will now be opened...")
        gate_2_open_sensor.enable_irq()
        verbose_print(
            "Gate 2 opened sensor interrupt service activated - push button pressed"
        )
        verbose_print("Lamp blinking started by gate 2 - PB.")
        gate_2.status = 1  # Set gate 2 status to opening.
    elif gate_2.status == 1:  # If gate 2 is opening and PB is pressed.
        verbose_print("Gate 2 is already opening...")
        verbose_print("PB did not affect the gate 2 motor.")
    elif gate_2.status == 2:  # If gate 2 is opened and PB is pressed.
        verbose_print("Gate 2 is already opened...")
        verbose_print("PB restarting the countdown timer.")
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        verbose_print("PB has restarted the countdown timer.")
    elif gate_2.status == 3:  # If gate 2 is closing and PB is pressed.
        gate_2_close_timer.deinit()  # Deactivate the timer
        gate_2.stop_gate()  # Stop gate 2 motor
        if gate_2_open_sensor.pin.value() == 0:
            gate_2.move_ccw()  # Open gate 2
            verbose_print("Gate 2 will now be opened...")
            gate_2_open_sensor.enable_irq()
            gate_2.status = 1  # Set gate 2 status to opening.
        else:
            gate_2.status = 2  # Set gate 2 status to opened
    else:
        verbose_print("Gate 2 is in an unknown state...")

    # Lamp control by PB
    if gate_1.status == 1 or gate_2.status == 1:  # If any gate is opening
        lamp_timer.deinit()  # Deactivate the timer
        lamp.value(0)  # Turn off the lamp
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)


def gate_1_open_sensor_handler():
    verbose_print("Gate 1 opened.")
    gate_1.stop_gate()  # Stop gate 1 motor
    gate_1.status = 2  # Set gate 1 status to opened
    if gate_2.status == 2 and gate_1.status == 2:  # If both gates are opened
        # Stop the lamp blinking
        lamp_timer.deinit()
        if lamp.value() == 0:
            lamp.on()
    gate_1_open_sensor.disable_irq()  # Disable gate 1 open sensor interrupt service
    verbose_print(
        "Gate 1 opened sensor interrupt service deactivated - reached open sensor."
    )
    verbose_print("Break sensor interrupt service deactivated.")
    gate_1_close_timer.deinit()
    gate_countdown_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    verbose_print("Gate 1 is fully opened. Restarting countdown timer...")


def gate_2_open_sensor_handler():
    verbose_print("Gate 2 opened.")
    gate_2.stop_gate()  # Stop gate 2 motor
    gate_2.status = 2  # Set gate 2 status to opened
    if gate_1.status == 2 and gate_2.status == 2:  # If both gates are opened
        # Stop the lamp blinking
        lamp_timer.deinit()
        if lamp.value() == 0:
            lamp.on()
    gate_2_open_sensor.disable_irq()  # Disable gate 2 open sensor interrupt service
    verbose_print(
        "Gate 2 opened sensor interrupt service deactivated - reached open sensor."
    )
    verbose_print("Break sensor interrupt service deactivated.")
    gate_2_close_timer.deinit()
    gate_countdown_timer.deinit()
    gate_countdown_timer.init(
        mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
    )
    verbose_print("Gate 2 is fully opened. Restarting countdown timer...")
    break_sensor.disable_irq()  # Disable break sensor interrupt service


def break_sensor_handler():
    verbose_print("Break sensor triggered.")

    if gate_1.status == 1:  # If gate 1 is opening
        # ignore the break sensor callback
        verbose_print("Gate 1 is opening, break sensor ignored.")
    elif gate_1.status == 2:  # If gate 1 is opened
        # reset the countdown timer
        verbose_print(
            "Gate 1 is opened, break sensor has restarted the countdown timer."
        )
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
    elif gate_1.status == 3:  # If gate 1 is closing
        gate_1_close_timer.deinit()  # Deactivate the timer
        gate_1.stop_gate()  # Stop gate 1 motor
        if gate_1_open_sensor.pin.value() == 0:
            gate_1.move_ccw()  # Open gate 1
            verbose_print("Gate 1 will now be opened...")
            gate_1_open_sensor.enable_irq()  # Re-enable gate 1 open sensor interrupt service
            gate_1.status = 1  # Set gate 1 status to opening.
        else:
            gate_1.status = 2  # Set gate 1 status to opened
    elif gate_1.status == 0:  # If gate 1 is closed
        # ignore the break sensor callback
        verbose_print("Gate 1 is closed, break sensor ignored.")
    else:
        verbose_print("Gate 1 is in an unknown state...")

    if gate_2.status == 1:  # If gate 2 is opening
        # ignore the break sensor callback
        verbose_print("Gate 2 is opening, break sensor ignored.")
    elif gate_2.status == 2:  # If gate 2 is opened
        # reset the countdown timer
        verbose_print(
            "Gate 2 is opened, break sensor has restarted the countdown timer."
        )
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
    elif gate_2.status == 3:  # If gate 2 is closing
        gate_2_close_timer.deinit()  # Deactivate the timer
        gate_2.stop_gate()  # Stop gate 2 motor
        if gate_2_open_sensor.pin.value() == 0:
            gate_2.move_ccw()
            # Open gate 2
            verbose_print("Gate 2 will now be opened...")
            gate_2_open_sensor.enable_irq()  # Re-enable gate 2 open sensor interrupt service
            gate_2.status = 1  # Set gate 2 status to opening.
        else:
            gate_2.status = 2  # Set gate 2 status to opened
    elif gate_2.status == 0:  # If gate 2 is closed
        # ignore the break sensor callback
        verbose_print("Gate 2 is closed, break sensor ignored.")
    else:
        verbose_print("Gate 2 is in an unknown state...")

    if gate_1.status == 2 and gate_2.status == 2:
        # If both gates are opened
        # Stop the lamp blinking
        lamp_timer.deinit()
        if lamp.value() == 0:
            lamp.on()


############################
# TIMER callback functions #
############################


def close_gates(timer):
    """
    This function is called when the countdown timer to keep gates opened expires.
    """

    if break_sensor.pin.value() == 1:
        verbose_print("Attempted to close gates but break sensor is active.")
        verbose_print("Restarting countdown timer...")
        gate_countdown_timer.deinit()
        gate_countdown_timer.init(
            mode=Timer.ONE_SHOT, period=KEEP_GATE_OPEN_TIME, callback=close_gates
        )
        gate_1.status = 2  # Set gate 1 status to opened
        gate_2.status = 2  # Set gate 2 status to opened
        return

    if gate_1.status == 2:  # If gate 1 is opened
        verbose_print("Gate 1 will now be closed...")
        gate_1.move_cw()
        gate_1_close_timer.init(
            mode=Timer.ONE_SHOT, period=GATE_1_TIME_TO_CLOSE, callback=close_gate_1
        )
        gate_1.status = 3  # Set gate 1 status to closing

    if gate_2.status == 2:  # If gate 2 is opened
        verbose_print("Gate 2 will now be closed...")
        gate_2.move_cw()
        gate_2_close_timer.init(
            mode=Timer.ONE_SHOT, period=GATE_2_TIME_TO_CLOSE, callback=close_gate_2
        )
        gate_2.status = 3  # Set gate 2 status to closing

    # If either gate is closing, Blink the lamp
    if gate_1.status == 3 or gate_2.status == 3:
        verbose_print("Lamp blinking started by timer.")
        lamp_timer
        lamp_timer.init(mode=Timer.PERIODIC, period=LAMP_PERIOD, callback=lamp_blink)
        verbose_print("Lamp blinking started by close gates timer.")
        break_sensor.enable_irq()  # Enable break sensor interrupt service
        verbose_print("Break sensor interrupt service activated by close gates timer.")


def close_gate_1(timer):
    gate_1.status = 0  # Set gate 1 status to closed
    gate_1.stop_gate()
    verbose_print("Gate 1 closed.")

    if gate_1.status == 0 and gate_2.status == 0:
        # If both gates are closed
        # Decativate the system
        verbose_print("Both gates are closed.")
        deactivate_system()


def close_gate_2(timer):
    gate_2.status = 0  # Set gate 2 status to closed
    gate_2.stop_gate()
    verbose_print("Gate 2 closed.")

    if gate_1.status == 0 and gate_2.status == 0:
        # If both gates are closed
        # Decativate the system
        verbose_print("Both gates are closed.")
        deactivate_system()


def lamp_blink(timer):
    lamp.on() if lamp.value() == 0 else lamp.off()


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
    lamp.value(0)  # Turn off the lamp


gate_1 = Gate(K1_MOTOR_1, K2_MOTOR_1)
gate_2 = Gate(K4_MOTOR_2, K3_MOTOR_2)
lamp = Pin(LAMP_PIN, Pin.OUT)

gate_1_open_sensor = PinDebounce(
    GATE_1_OPEN_SENSOR_PIN, gate_1_open_sensor_handler, debounce_time=3000
)
gate_2_open_sensor = PinDebounce(
    GATE_2_OPEN_SENSOR_PIN, gate_2_open_sensor_handler, debounce_time=3000
)
break_sensor = PinDebounce(BREAK_SENSOR_PIN, break_sensor_handler, debounce_time=800)
open_gate_switch = PinDebounce(
    OPEN_GATE_SWITCH_PIN, open_gate_switch_handler, debounce_time=500
)

gate_countdown_timer = Timer(0)
gate_1_close_timer = Timer(1)
gate_2_close_timer = Timer(2)
lamp_timer = Timer(3)

# A WLAN interface must be active to send()/recv() via ESP-NOW
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # ESP-NOW does not have to be connected to a network
# Initialize and activate ESP-NOW
e = espnow.ESPNow()
e.active(True)


def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            verbose_print("No more messages.")
            verbose_print(e.peers_table)
            return
        verbose_print(mac, msg.hex())
        if msg == b"\x01":
            # If the message is 0x01, open the gate
            open_gate_switch_handler()


lamp.off()

# Enable the ESP-NOW interrupt service
e.irq(recv_cb)
