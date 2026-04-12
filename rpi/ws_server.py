#!/usr/bin/env python3
"""
SmartDryer WebSocket Relay Server — port 8082
Receives data from the detector (index.html) and broadcasts
to all dashboard clients in realtime.
Zero Firebase reads. Purely local over WiFi.
"""

import asyncio
import json
import websockets
import datetime

PORT = 8082
clients = set()        # dashboard viewers
latest_state = {}      # last known state — sent to new joiners immediately

def log(msg):
    t = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"  [{t}] {msg}")

async def handler(websocket):
    global latest_state
    clients.add(websocket)
    client_ip = websocket.remote_address[0] if websocket.remote_address else '?'
    log(f"Client connected: {client_ip} (total: {len(clients)})")

    # Send latest state immediately to new client
    if latest_state:
        try:
            await websocket.send(json.dumps(latest_state))
        except Exception:
            pass

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                msg_type = msg.get('type','')

                # ── Detector sending data ────────────────────────
                if msg_type in ('sensor','result','status'):
                    # Merge into latest state
                    latest_state.update(msg)
                    latest_state['updated_at'] = datetime.datetime.now().isoformat()

                    if msg_type == 'sensor':
                        log(f"Sensor: {msg.get('temp','?')}°C  {msg.get('hum','?')}%")
                    elif msg_type == 'result':
                        log(f"Result: {msg.get('label','?')} ({round(msg.get('conf',0)*100)}%)")

                    # Broadcast to ALL other clients (dashboards)
                    dead = set()
                    for client in clients:
                        if client != websocket:
                            try:
                                await client.send(json.dumps(latest_state))
                            except Exception:
                                dead.add(client)
                    clients -= dead

                # ── Dashboard requesting current state ───────────
                elif msg_type == 'get_state':
                    await websocket.send(json.dumps(latest_state or {'type':'empty'}))

            except json.JSONDecodeError:
                pass
            except Exception as e:
                log(f"Error: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        log(f"Client disconnected: {client_ip} (total: {len(clients)})")

async def main():
    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║   SmartDryer WebSocket Relay — Port {PORT}  ║")
    print(f"  ║   Zero Firebase reads for realtime data  ║")
    print(f"  ╚══════════════════════════════════════════╝\n")
    print(f"  Detector  → ws://localhost:{PORT}")
    print(f"  Dashboard → ws://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop\n")

    async with websockets.serve(handler, '0.0.0.0', PORT):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n  WebSocket server stopped.')
