import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://127.0.0.1:8000/ws/algorithm") as ws:
        await ws.send(json.dumps({
            "action": "run",
            "algorithm": "prim",
            "city_id": "bengaluru",
            "params": {"speed_ms": 1}
        }))
        for i in range(5):
            msg = json.loads(await ws.recv())
            kind = msg.get("delta", {}).get("kind", "N/A")
            print(f"Message {i}: type={msg['type']}, kind={kind}")
        await ws.close()
        print("WebSocket test PASSED!")

asyncio.run(test())
