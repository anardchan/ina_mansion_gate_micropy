import machine as esp8266  # type: ignore # Import the machine module as esp8266

ir = esp8266.Pin(15, esp8266.Pin.IN)  # Create a Pin object for GPIO16 and set it as an input pin
led = esp8266.Pin(2, esp8266.Pin.OUT)  # Create a Pin object for GPIO15 and set it as an output pin

def ir_callback(pin):
    if pin.value() == 0:
        print("IR does not detect anything")
        led.on()
    else:
        print("IR detected something")
        led.off()

# def ir_does_not_detect_anything(pin):
#     print("IR does not detect anything")
#     led.on()

ir.irq(trigger=esp8266.Pin.IRQ_FALLING | esp8266.Pin.IRQ_RISING, handler=ir_callback)
