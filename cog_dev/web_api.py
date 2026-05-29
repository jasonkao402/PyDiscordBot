# web_api.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
import time
from cog_dev.moderation import PendingMessageManager

app = FastAPI()
pending_manager: PendingMessageManager # to be set by askAI cog when initialized

# WebSocket endpoint to push updates to admin page
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: str):
        for connection in self.active_connections:
            await connection.send_text(data)

ws_manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial list
        await push_update()
        while True:
            # Keep connection alive; updates are pushed when state changes
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

import time

async def push_update():
    now_mono = time.monotonic()
    messages = pending_manager.get_all()
    data = []
    for m in messages:
        d = m.to_dict()
        if d["actionState"] == 0:  # ActionState.DEFAULT
            d["remaining"] = max(0, d["ttl"] - (now_mono - d["received_at"]))
        else:
            d["remaining"] = 0
        data.append(d)
    await ws_manager.broadcast(json.dumps(data))

# REST actions
from pydantic import BaseModel

class EditSubmit(BaseModel):
    msg_id: str
    new_content: str

@app.post("/action/send")
async def action_send(msg_id: str):
    await pending_manager.send_immediately(msg_id)
    await push_update()
    return {"ok": True}

@app.post("/action/reject")
async def action_reject(msg_id: str):
    await pending_manager.reject(msg_id)
    await push_update()
    return {"ok": True}

@app.post("/action/hold")
async def action_hold(msg_id: str):
    await pending_manager.hold(msg_id)
    await push_update()
    return {"ok": True}

@app.post("/action/submit_edit")
async def action_submit_edit(edit: EditSubmit):
    await pending_manager.submit_edited(edit.msg_id, edit.new_content)
    await push_update()
    return {"ok": True}

# Serve the admin page (minimal HTML)
@app.get("/", response_class=FileResponse)
async def get_index():
    return FileResponse("cog_dev/templates/index.html")