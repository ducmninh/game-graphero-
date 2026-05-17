import socket
import struct
import threading
import json
import time


def _get_all_broadcast_addresses():
    """
    Lấy tất cả broadcast address của các interface đang hoạt động
    (bao gồm cả Radmin VPN 26.x.x.x, LAN 192.168.x.x, ...).
    Fallback về 255.255.255.255 nếu không lấy được.
    """
    broadcasts = set()
    try:
        import socket as _s
        # Kết nối UDP giả để lấy IP local chính
        s = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Tạo broadcast từ IP local (giả sử /24)
        parts = local_ip.split('.')
        broadcasts.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
    except:
        pass

    # Thử dùng netifaces nếu có
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    bcast = addr.get('broadcast')
                    if bcast and bcast != '127.255.255.255':
                        broadcasts.add(bcast)
    except ImportError:
        pass
    except:
        pass

    # Thêm các dải phổ biến của Radmin VPN và LAN
    broadcasts.update([
        '26.255.255.255',    # Radmin VPN default range
        '25.255.255.255',    # Hamachi
        '192.168.1.255',
        '192.168.0.255',
        '10.0.0.255',
        '172.16.0.255',
        '255.255.255.255',   # General broadcast
    ])

    return list(broadcasts)


class NetworkManager:
    def __init__(self, game):
        self.game = game
        self.host = '0.0.0.0'
        self.port = 5555
        self.socket = None
        self.is_host = False
        self.running = False
        self.clients = []
        self.peer_data = {}
        self.host_error = ""
        self.beacon_running = False
        self.listener_running = False
        self.discovered_rooms = {}   # { ip: {level, my_id, last_seen} }

    # ------------------------------------------------------------------
    def stop(self):
        self.running = False
        self.stop_beacon()
        self.stop_lobby_listener()
        if self.socket:
            try: self.socket.close()
            except: pass
            self.socket = None
        self.clients.clear()
        self.peer_data.clear()
        self.is_host = False

    # ------------------------------------------------------------------
    def start_host(self):
        self.stop()
        self.host_error = ""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.is_host = True
            self.running = True
            threading.Thread(target=self._accept_clients, daemon=True).start()
            ip = socket.gethostbyname(socket.gethostname())
            print(f"[NET] Server started on {ip}:{self.port}")
            return True
        except OSError as e:
            self.host_error = f"Loi khoi dong server: {e}"
            print(self.host_error)
            return False

    # ------------------------------------------------------------------
    def connect(self, ip):
        self.stop()
        self.host_error = ""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(5.0)
            self.socket.connect((ip, self.port))
            self.socket.settimeout(None)
            self.running = True
            threading.Thread(target=self._receive_data, args=(self.socket,), daemon=True).start()
            return True
        except Exception as e:
            self.host_error = f"Ket noi that bai: {e}"
            print(self.host_error)
            return False

    # ------------------------------------------------------------------
    def _accept_clients(self):
        while self.running:
            try:
                client, addr = self.socket.accept()
                self.clients.append(client)
                print(f"[NET] Client connected: {addr}")
                threading.Thread(target=self._receive_data, args=(client,), daemon=True).start()
            except:
                break

    def _receive_data(self, sock):
        while self.running:
            try:
                data = sock.recv(4096).decode('utf-8')
                if not data:
                    break
                for line in data.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        p_id = msg.get("id")
                        if p_id:
                            self.peer_data[p_id] = msg
                    except:
                        pass
            except:
                break

    # ------------------------------------------------------------------
    def send_update(self, player_data):
        if not self.socket:
            return
        try:
            data = (json.dumps(player_data) + '\n').encode('utf-8')
        except:
            return
        if self.is_host:
            for client in list(self.clients):
                try:
                    client.send(data)
                except:
                    try: self.clients.remove(client)
                    except: pass
        else:
            try:
                self.socket.send(data)
            except:
                self.running = False

    # ==================================================================
    # AUTO DISCOVERY — broadcast on ALL interfaces (Radmin, LAN, etc.)
    # ==================================================================
    def start_beacon(self):
        self.beacon_running = True
        threading.Thread(target=self._send_beacon, daemon=True).start()

    def stop_beacon(self):
        self.beacon_running = False

    def _send_beacon(self):
        """Phát tín hiệu UDP trên TẤT CẢ các interface mạng."""
        while self.beacon_running and self.running:
            broadcasts = _get_all_broadcast_addresses()
            payload = json.dumps({
                "game_mode": "Grab Hero",
                "level": getattr(self.game, 'level_name', 'Sanh Cho') if self.game else 'Sanh Cho',
                "my_id": getattr(self.game, 'my_id', 0) if self.game else 0
            }).encode('utf-8')

            for bcast in broadcasts:
                try:
                    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    udp_sock.settimeout(0.2)
                    udp_sock.sendto(payload, (bcast, 5556))
                    udp_sock.close()
                except:
                    pass

            time.sleep(1.0)

    # ------------------------------------------------------------------
    def start_lobby_listener(self):
        self.listener_running = True
        self.discovered_rooms = {}
        threading.Thread(target=self._listen_for_beacons, daemon=True).start()

    def stop_lobby_listener(self):
        self.listener_running = False

    def _listen_for_beacons(self):
        """Lắng nghe tín hiệu UDP từ Host trên cổng 5556."""
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_sock.bind(('0.0.0.0', 5556))
            udp_sock.settimeout(0.5)
        except Exception as e:
            print(f"[NET] Beacon listener failed to bind: {e}")
            return

        print("[NET] Beacon listener started on 0.0.0.0:5556")
        while self.listener_running:
            try:
                data, addr = udp_sock.recvfrom(2048)
                sender_ip = addr[0]
                msg = json.loads(data.decode('utf-8'))
                if msg.get("game_mode") == "Grab Hero":
                    self.discovered_rooms[sender_ip] = {
                        "level":     msg.get("level", "Sanh Cho"),
                        "my_id":     msg.get("my_id", 0),
                        "last_seen": time.time()
                    }
                    print(f"[NET] Discovered room at {sender_ip}")
            except socket.timeout:
                pass
            except Exception:
                pass

            # Dọn phòng không phát tín hiệu quá 5 giây
            now = time.time()
            stale = [ip for ip, info in list(self.discovered_rooms.items())
                     if now - info["last_seen"] > 5.0]
            for ip in stale:
                self.discovered_rooms.pop(ip, None)

        try:
            udp_sock.close()
        except:
            pass
        print("[NET] Beacon listener stopped.")
