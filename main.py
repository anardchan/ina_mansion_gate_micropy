import machine # type: ignore

push_button = machine.Pin(17, machine.Pin.IN)
led = machine.Pin(16, machine.Pin.OUT)

led.off()


def push_button_callback(pin):
    if push_button.value() == 0:
        led.off()
        print("Button released. Button value: ", push_button.value())
    else:
        led.on()
        print("Button pressed. Button value: ", push_button.value())


push_button.irq(
    trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING,
    handler=push_button_callback,
)
