import json
import asyncio
from fastapi import WebSocket
from starlette.websockets import WebSocketState


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.acquaintance_connections = {}
        self.waiting_for_response = {}

    async def wait_for_message(self, device_id: str, request_id: str, timeout: float = 10.0):
        """Wait for a specific message from a WebSocket client."""
        future = asyncio.Future()
        self.waiting_for_response[request_id] = future
        try:
            # Wait for the future to be set by the message handler
            await asyncio.wait_for(future, timeout=timeout)
            return future.result()
        except asyncio.TimeoutError:
            raise TimeoutError(f"Timed out waiting for response to {request_id}")
        finally:
            del self.waiting_for_response[request_id]

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        queue = asyncio.Queue()
        self.active_connections[websocket] = queue
        asyncio.create_task(self._listen(websocket, queue))

    async def _listen(self, websocket: WebSocket, queue: asyncio.Queue):
        try:
            while True:
                data = await websocket.receive_text()
                await queue.put(data)
                # Check if this is a response to a waiting request
                message = json.loads(data)
                # print("RECEIVING MESSAGE", message)
                request_id = message.get("request_id")
                if request_id and request_id in self.waiting_for_response:
                    self.waiting_for_response[request_id].set_result(message)
                    print(self.waiting_for_response)
        except Exception as e:
            await self.disconnect(websocket)
            print(f"WebSocket disconnected: {e}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        if websocket in self.active_connections:
            # print("SENDING MESSAGE", message)
            await websocket.send_text(message)

    async def send_personal_message_to_device_id(self, message: str, device_id: str):
        if device_id in self.acquaintance_connections:
            await self.acquaintance_connections[device_id].send_text(message)

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

            for device_id, ws in self.acquaintance_connections.items():
                if ws == websocket:
                    del self.acquaintance_connections[device_id]

            # ! del  request_id  (waiting_for_response)
            # for request_id, ws in self.waiting_for_response.items():
            #     if ws == websocket:
            #         del self.acquaintance_connections[request_id]

            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
                print("WebSocket closed")
            else:
                print("WebSocket was already closed")

    async def get_message(self, websocket: WebSocket):
        if websocket in self.active_connections:
            queue = self.active_connections[websocket]
            return await queue.get()


manager = ConnectionManager()
