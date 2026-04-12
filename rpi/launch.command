#!/bin/bash
cd "$(dirname "$0")"
source yenv/bin/activate 2>/dev/null || true

# Install websockets if needed
pip install websockets -q 2>/dev/null

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       SmartDryer — Starting All Services         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Kill any existing servers on these ports
lsof -ti:8080 | xargs kill -9 2>/dev/null; sleep 0.3
lsof -ti:8081 | xargs kill -9 2>/dev/null; sleep 0.3
lsof -ti:8082 | xargs kill -9 2>/dev/null; sleep 0.3

# Start SMS proxy
echo "▶ Starting SMS proxy (port 8081)..."
python3 sms_proxy.py &
SMS_PID=$!

# Start WebSocket relay
echo "▶ Starting WebSocket relay (port 8082)..."
python3 ws_server.py &
WS_PID=$!

sleep 1

# Start web server
echo "▶ Starting web server (port 8080)..."
echo ""
echo "  ┌─ DETECTOR APP ──────────────────────────────────┐"
echo "  │  http://localhost:8080                           │"
echo "  │  http://$LOCAL_IP:8080                      │"
echo "  ├─ USER DASHBOARD ───────────────────────────────┤"
echo "  │  http://localhost:8080/dashboard.html            │"
echo "  │  http://$LOCAL_IP:8080/dashboard.html        │"
echo "  ├─ SERVICES ─────────────────────────────────────┤"
echo "  │  SMS Proxy:  http://localhost:8081               │"
echo "  │  WS Relay:   ws://localhost:8082                 │"
echo "  └─────────────────────────────────────────────────┘"
echo ""
echo "  Firebase used for: Settings + Validation history only"
echo "  Realtime data via: Local WebSocket (zero Firebase reads)"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Kill all on Ctrl+C
trap "echo ''; echo 'Stopping all services...'; kill $SMS_PID $WS_PID 2>/dev/null; exit 0" INT TERM

python3 server.py

kill $SMS_PID $WS_PID 2>/dev/null
