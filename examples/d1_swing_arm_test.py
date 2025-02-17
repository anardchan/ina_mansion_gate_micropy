import machine as esp8266  # type: ignore
import time

led_enable = esp8266.Pin(16, esp8266.Pin.OUT)  # D2
led_direction = esp8266.Pin(15, esp8266.Pin.OUT)  # D10
motor_enable = esp8266.Pin(13, esp8266.Pin.IN)  # D11
motor_direction = esp8266.Pin(12, esp8266.Pin.IN)  # D12


def motor_enable_callback(pin):
    time.sleep(0.1)
    if pin.value() == 1:
        print("Motor is on")
        led_enable.on()
    else:
        print("Motor is off")
        led_enable.off()


def motor_direction_callback(pin):
    time.sleep(0.1)
    if pin.value() == 1:
        print("CC Direction")
        led_direction.on()
    else:
        print("CCW Direction")
        led_direction.off()


motor_enable.irq(
    trigger=esp8266.Pin.IRQ_FALLING | esp8266.Pin.IRQ_RISING,
    handler=motor_enable_callback,
)
motor_direction.irq(
    trigger=esp8266.Pin.IRQ_FALLING | esp8266.Pin.IRQ_RISING,
    handler=motor_direction_callback,
)
