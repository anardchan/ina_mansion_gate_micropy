import network
import socket
import machine
import _thread
from machine import Pin, Timer
import dns_server

led = Pin(4, Pin.OUT)
CUSTOM_DOMAIN = "open.button"
HTML_PAGE = """<!DOCTYPE html>
<html><head><title>ESP32</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f0f0f0}button{width:200px;height:200px;font-size:2em;background:#4CAF50;color:white;border:none;border-radius:16px}</style></head>
<body><button id="btn">OPEN</button>
<script>
const b=document.getElementById('btn');
function send(u){fetch(u).catch(e=>{})}
b.ontouchstart=b.onmousedown=(e)=>{e.preventDefault();send('/on')};
b.ontouchend=b.onmouseup=b.onmouseleave=(e)=>{e.preventDefault();send('/off')};
</script></body></html>
"""

# Start Access Point with password
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="ESP32-AP", password="12345678", authmode=network.AUTH_WPA_WPA2_PSK)
ip = ap.ifconfig()[0]

# Start DNS server
_thread.start_new_thread(dns_server.start_dns_server, (ip,))

# Web server control
server_running = False
client_connected = False
check_timer = Timer(-1)

def start_server():
    global server_running
    if server_running:
        return
    server_running = True

    s = socket.socket()
    s.bind(('0.0.0.0', 80))
    s.listen(1)
    s.settimeout(1)

    def serve():
        global server_running, client_connected
        while client_connected:
            try:
                cl, addr = s.accept()
                req = cl.recv(1024).decode()
                if '/on' in req:
                    led.value(1)
                    cl.send('HTTP/1.1 200 OK\r\n\r\nLED ON')
                elif '/off' in req:
                    led.value(0)
                    cl.send('HTTP/1.1 200 OK\r\n\r\nLED OFF')
                else:
                    cl.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
                    cl.sendall(HTML_PAGE)
                cl.close()
            except:
                pass
        s.close()
        led.value(0)
        server_running = False

    _thread.start_new_thread(serve, ())

def check_clients(timer):
    global client_connected
    stations = ap.status('stations')
    if stations:
        if not client_connected:
            client_connected = True
            start_server()
    else:
        client_connected = False

check_timer.init(period=2000, mode=Timer.PERIODIC, callback=check_clients)
print("ESP32 AP started. Connect to Wi-Fi 'ESP32-AP' (PW: 12345678), then go to http://" + CUSTOM_DOMAIN)
