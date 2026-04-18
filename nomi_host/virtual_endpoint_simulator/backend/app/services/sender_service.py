import json
import socket
from typing import Any, Dict, Tuple


class PacketSender:
    def send_packet(self, packet: Dict[str, Any], host: str, port: int, timeout: float = 3.0, protocol: str = "tcp") -> Tuple[bool, str]:
        try:
            payload = (json.dumps(packet, ensure_ascii=False) + "\n").encode("utf-8")
            
            if protocol.lower() == "udp":
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        bytes_sent = sock.sendto(payload, (host, port))
                        # print(f"DEBUG: UDP Sent {bytes_sent} bytes to {host}:{port}")
                        return True, "ok"
                except Exception as e:
                     print(f"DEBUG: UDP Send Error: {e}")
                     return False, str(e)
            else:
                with socket.create_connection((host, port), timeout=timeout) as sock:
                    sock.sendall(payload)
                return True, "ok"
        except Exception as exc:
            print(f"DEBUG: General Send Error: {exc}")
            return False, str(exc)

    def check_connection(self, host: str, port: int, timeout: float = 1.0, protocol: str = "tcp") -> bool:
        """
        Attempts to connect to the target host:port.
        Returns True if successful, False otherwise.
        Does not send any data.
        """
        try:
            if protocol.lower() == "udp":
                # UDP is connectionless; assume reachable for now or implement a handshake
                # Just check if we can resolve the host
                socket.gethostbyname(host)
                return True
            else:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
        except (OSError, ConnectionRefusedError, socket.timeout):
            return False

