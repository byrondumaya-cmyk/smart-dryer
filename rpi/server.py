#!/usr/bin/env python3
"""
SmartDryer Web Server
- Serves all files with no-cache headers
- Binds to 0.0.0.0 so any device on WiFi can connect
- Serves BACKUP folder for local image access
- Port 8080
"""
import http.server
import socketserver
import socket
import os

PORT = 8080

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma',        'no-cache')
        self.send_header('Expires',       '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, fmt, *args):
        code = args[1] if len(args) > 1 else '?'
        path = args[0].split()[1] if len(args) > 0 and ' ' in str(args[0]) else str(args[0])
        # Only log non-image requests to reduce noise
        if not any(path.endswith(ext) for ext in ['.jpg','.jpeg','.png','.ico']):
            print(f"  [{code}] {path}")

if __name__ == '__main__':
    # Get local network IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = 'localhost'

    # Check BACKUP folder exists
    backup_path = os.path.join(os.path.dirname(__file__), 'BACKUP')
    if os.path.exists(backup_path):
        print(f"  ✅ BACKUP folder found — serving local images")
    else:
        print(f"  ⚠️  BACKUP folder not found at {backup_path}")
        print(f"     Run setup_backup.sh to link it")

    with socketserver.TCPServer(('0.0.0.0', PORT), NoCacheHandler) as httpd:
        httpd.socket.setsockopt(socketserver.socket.SOL_SOCKET,
                                socketserver.socket.SO_REUSEADDR, 1)
        print(f"\n  ┌─ DETECTOR APP ──────────────────────────────────┐")
        print(f"  │  http://localhost:{PORT}                           │")
        print(f"  │  http://{local_ip}:{PORT}                     │")
        print(f"  ├─ USER DASHBOARD ────────────────────────────────┤")
        print(f"  │  http://localhost:{PORT}/dashboard.html            │")
        print(f"  │  http://{local_ip}:{PORT}/dashboard.html      │")
        print(f"  └─────────────────────────────────────────────────┘")
        print(f"\n  Share Network URL with anyone on same WiFi!")
        print(f"  Press Ctrl+C to stop\n")
        httpd.serve_forever()
