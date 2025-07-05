import network

sta = network.WLAN(network.STA_IF) 
sta.active(True)

mac = sta.config('mac')

print("MAC Address:", ':'.join('%02x' % b for b in mac))