import time
import network  # type: ignore
import espnow  # type: ignore
from machine import Pin, Timer  # type: ignore
from config import CHANNEL

##################
# PIN ASSIGNMENT #
##################
LAMP_PIN = 32
K1_MOTOR_1 = 33
K2_MOTOR_1 = 25
K4_MOTOR_2 = 26
K3_MOTOR_2 = 27
PASS_SENSOR_PIN = 34

################
# Timer Values #
################
TICK_MS = 100
GATE_OPEN_TIME = 15.0
GATE1_CLOSE_TIME = 11.1
GATE2_CLOSE_TIME = 13
WAIT_BEFORE_CLOSE = 30.0
DEBOUNCE_MS = 500

# Convert to ticks (0.1s units)
OPEN_TICKS = int(GATE_OPEN_TIME * 10)
GATE1_CLOSE_TICKS = int(GATE1_CLOSE_TIME * 10)
GATE2_CLOSE_TICKS = int(GATE2_CLOSE_TIME * 10)
WAIT_TICKS = int(WAIT_BEFORE_CLOSE * 10)


##############
# Gate Class #
##############
class Gate:
    def __init__(self, motor_enable, motor_direction):
        self.motor_enable = Pin(motor_enable, Pin.OUT)
        self.motor_direction = Pin(motor_direction, Pin.OUT)
        self.status = 0  # 0 = closed, 1 = opening, 2 = opened, 3 = closing

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


#############
# Globals   #
#############
gate1 = Gate(K1_MOTOR_1, K2_MOTOR_1)
gate2 = Gate(K4_MOTOR_2, K3_MOTOR_2)
lamp = Pin(LAMP_PIN, Pin.OUT)

STATE_CLOSED = 0
STATE_OPENING = 1
STATE_WAITING = 2
STATE_CLOSING = 3

state = STATE_CLOSED
elapsed = 0
wait_remaining = WAIT_TICKS
closing_elapsed = 0
last_sensor_irq = 0

################
# Lamp Config  #
################
LAMP_BLINK_MS = 500  # Blink interval in ms (configurable)
lamp_tick_accum = 0  # accumulator for blinking


######################
# Helper Functions   #
######################
def debug(msg):
    print("[DEBUG]", msg)


def lamp_update():
    global lamp_tick_accum
    lamp_tick_accum += TICK_MS

    if state in (STATE_OPENING, STATE_CLOSING):
        if lamp_tick_accum >= LAMP_BLINK_MS:
            lamp.value(not lamp.value())  # toggle
            lamp_tick_accum = 0
    elif state == STATE_WAITING:
        lamp.on()
        lamp_tick_accum = 0
    else:
        lamp.off()
        lamp_tick_accum = 0


def start_opening(reopen_ticks=None):
    global state, elapsed, wait_remaining
    state = STATE_OPENING
    elapsed = 0
    debug("Gates opening")
    gate1.move_ccw()
    gate2.move_ccw()
    if reopen_ticks:
        debug("Reopening for %d ticks" % reopen_ticks)
        wait_remaining = WAIT_TICKS
        gate1.reopen_ticks = min(reopen_ticks, GATE1_CLOSE_TICKS)
        gate2.reopen_ticks = min(reopen_ticks, GATE2_CLOSE_TICKS)
    else:
        gate1.reopen_ticks = OPEN_TICKS
        gate2.reopen_ticks = OPEN_TICKS


def start_closing():
    global state, closing_elapsed
    state = STATE_CLOSING
    closing_elapsed = 0
    debug("Gates closing")
    gate1.move_cw()
    gate2.move_cw()


def on_open_complete():
    global state, wait_remaining
    state = STATE_WAITING
    wait_remaining = WAIT_TICKS
    debug("Gates fully open. Starting wait timer: %d ticks" % wait_remaining)


def on_close_complete():
    global state
    state = STATE_CLOSED
    debug("Gates fully closed")


############################
# Timer Ticker (100 ms)    #
############################
def ticker_cb(timer):
    global state, elapsed, wait_remaining, closing_elapsed

    if state == STATE_OPENING:
        elapsed += 1
        if elapsed >= max(gate1.reopen_ticks, gate2.reopen_ticks):
            gate1.stop_gate()
            gate2.stop_gate()
            on_open_complete()

    elif state == STATE_WAITING:
        if wait_remaining > 0:
            wait_remaining -= 1
            if wait_remaining % 10 == 0:  # log every 1s
                debug("Wait remaining: %.1fs" % (wait_remaining / 10))
        if wait_remaining == 0:
            start_closing()

    elif state == STATE_CLOSING:
        closing_elapsed += 1
        if closing_elapsed >= max(GATE1_CLOSE_TICKS, GATE2_CLOSE_TICKS):
            gate1.stop_gate()
            gate2.stop_gate()
            on_close_complete()

    lamp_update()


ticker = Timer(0)
ticker.init(period=TICK_MS, mode=Timer.PERIODIC, callback=ticker_cb)


###########################
# IRQ Handlers            #
###########################
def espnow_cb(e):
    while True:
        mac, msg = e.irecv(0)
        if not mac:
            return
        if msg == b"\x01":
            debug("ESP-NOW 0x1 received")
            handle_trigger_event("espnow")


def pass_sensor_cb(pin):
    global last_sensor_irq
    now = time.ticks_ms()
    if time.ticks_diff(now, last_sensor_irq) < DEBOUNCE_MS:
        return
    last_sensor_irq = now

    val = pin.value()
    if val == 1:
        debug("Pass-through HIGH")
        handle_trigger_event("sensor_high")
    else:
        debug("Pass-through LOW")
        handle_trigger_event("sensor_low")


###########################
# Event Handler           #
###########################
def handle_trigger_event(src):
    global state, closing_elapsed, wait_remaining

    if src == "espnow":
        if state == STATE_CLOSED:
            start_opening()
        elif state == STATE_OPENING:
            debug("Ignored ESP-NOW (already opening)")
        elif state == STATE_WAITING:
            wait_remaining = WAIT_TICKS
            debug("Wait timer reset due to ESP-NOW")
        elif state == STATE_CLOSING:
            start_opening(reopen_ticks=closing_elapsed + 1)

    elif src == "sensor_high":
        if state == STATE_WAITING:
            debug("Pass-through active: freezing timer")
            # timer frozen (no decrement while high)
        elif state == STATE_CLOSING:
            start_opening(reopen_ticks=closing_elapsed + 1)

    elif src == "sensor_low":
        if state == STATE_WAITING:
            wait_remaining = WAIT_TICKS
            debug("Pass-through cleared: wait timer reset")


###########################
# ESP-NOW Setup           #
###########################
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=CHANNEL)
sta.disconnect()

mac = sta.config("mac")
# print(f"MAC Address: {':'.join("%02x" % b for b in mac)}")

e = espnow.ESPNow()
e.active(True)
e.irq(espnow_cb)

###########################
# Sensor Setup            #
###########################
pass_sensor = Pin(PASS_SENSOR_PIN, Pin.IN)
pass_sensor.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=pass_sensor_cb)

lamp.off()
debug("System initialized. State=CLOSED")
