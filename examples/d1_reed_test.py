import machine as esp8266 # type: ignore

reed_pin = esp8266.Pin(15, esp8266.Pin.IN)
led = esp8266.Pin(2, esp8266.Pin.OUT)

def reed_callback(pin):
    if reed_pin.value() == 0:
        led.on()
    else:
        led.off()

reed_pin.irq(trigger=esp8266.Pin.IRQ_FALLING | esp8266.Pin.IRQ_RISING, handler=reed_callback)
