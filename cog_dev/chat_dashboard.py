from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel  # 新增這行
from typing import Dict, List
import asyncio
import json

app = FastAPI()

class ReplyPayload(BaseModel):
    reply: str

# 客戶端管理器
class ConnectionManager:
    def __init__(self):
        self.user_connections: Dict[str, WebSocket] = {}  # 單一使用者 session
        self.dashboard_connections: List[WebSocket] = []  # 所有 dashboard clients

    async def connect_user(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.user_connections[session_id] = websocket

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.append(websocket)

    def disconnect_user(self, session_id: str):
        if session_id in self.user_connections:
            del self.user_connections[session_id]

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)

    async def send_to_user(self, session_id: str, message: str):
        websocket = self.user_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)

    async def broadcast_to_dashboard(self, session_id: str, reply: str):
        payload = {
            "session_id": session_id,
            "reply": reply
        }
        for websocket in self.dashboard_connections:
            await websocket.send_text(json.dumps(payload))

manager = ConnectionManager()

# 靜態與模板設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/{session_id}")
async def websocket_user_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect_user(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"🧑‍💻 Received user control [{session_id}]: {data}")
    except WebSocketDisconnect:
        manager.disconnect_user(session_id)

@app.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    print(f"🔌 Dashboard connected, total connections: {len(manager.dashboard_connections)}")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            print(f"📋 Dashboard action: {payload}")
            # 處理來自 Dashboard 的操作
            if payload.get("action") == "SEND":
                session_id = payload.get("session_id")
                reply = payload.get("reply")
                await manager.send_to_user(session_id, reply)
                print(f"✅ Reply sent to user {session_id}")
            
            # 可以增加 CANCEL 處理
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)

# 修改 send_reply：只發送到儀表板，不立即發送給用戶
@app.post("/send_reply/{session_id}")
async def send_reply(session_id: str, payload: ReplyPayload):
    print(f"💬 Received request to send reply to {session_id}: {payload.reply}")
    print(f"📊 Dashboard connections: {len(manager.dashboard_connections)}")
    
    # Only broadcast to dashboard for review
    await manager.broadcast_to_dashboard(session_id, payload.reply)
    print(f"📣 Broadcasted to dashboard for session {session_id}")
    return {"message": "Reply queued for review."}

# Entry Point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chat_dashboard:app", host="127.0.0.1", port=8000, reload=True)
