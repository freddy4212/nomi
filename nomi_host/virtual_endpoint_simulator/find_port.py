import socket
import sys


def find_free_port(start_port=8000):
    port = start_port
    while port < 65535:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            s.close()
            print(port)
            return
        except OSError:
            port += 1

if __name__ == "__main__":
    start_port = 8000
    if len(sys.argv) > 1:
        start_port = int(sys.argv[1])
    find_free_port(start_port)
