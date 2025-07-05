import socket

def start_dns_server(ip='192.168.4.1'):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(('0.0.0.0', 53))
    print("DNS server started")

    while True:
        try:
            data, addr = udp.recvfrom(512)
            request_id = data[0:2]
            response = request_id + b'\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00'
            query = data[12:]
            response += query
            response += b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'
            response += bytes(map(int, ip.split('.')))
            udp.sendto(response, addr)
        except Exception as e:
            print("DNS error:", e)
