import asyncio

import websockets


async def main():
    async with websockets.connect("ws://websocket:9001/factory/all") as websocket:
        await websocket.send('{"camera_id":1, "data":"ping"}')


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
