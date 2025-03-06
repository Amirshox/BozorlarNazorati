from fastapi import FastAPI, WebSocket

app = FastAPI()

# Create a dictionary to store WebSocket connections for each room
rooms = {}
roi_camera_rooms = {}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()

    # Create a room if it doesn't exist
    if room_id not in rooms:
        rooms[room_id] = []
    rooms[room_id].append(websocket)
    print(rooms)

    try:
        while True:
            data = await websocket.receive_text()

            # Send the message to all clients in the room
            for client in rooms[room_id]:
                await client.send_text(data)
    except Exception as e:
        print("Exception", e)
        rooms[room_id].remove(websocket)


@app.websocket("/{roicamera_id}/connect")
async def factory_all_endpoint(websocket: WebSocket, roicamera_id):
    await websocket.accept()

    # Create a room if it doesn't exist
    if roicamera_id not in roi_camera_rooms:
        roi_camera_rooms[roicamera_id] = []
    roi_camera_rooms[roicamera_id].append(websocket)
    print(roi_camera_rooms)

    try:
        while True:
            data = await websocket.receive_text()

            # Send the message to all clients in the room
            for client in roi_camera_rooms[roicamera_id]:
                await client.send_text(data)
    except Exception as e:
        print("Exception", e)
        roi_camera_rooms[roicamera_id].remove(websocket)
