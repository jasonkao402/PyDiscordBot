# web_api.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
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

async def push_update():
    messages = pending_manager.get_all()
    data = []
    for m in messages:
        data.append({
            "uid": m.uid,
            "content": m.content,
            "held": m.stateAction,
            "user_name": m.display_name,
            "received_at": m.received_at,
            "persona": m.persona_name,
            "token_usage": m.token_usage
        })
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

@app.post("/action/discard")
async def action_discard(msg_id: str):
    await pending_manager.discard(msg_id)
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
@app.get("/", response_class=HTMLResponse)
async def admin_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hachiya Moderation</title>
        <script>
            let ws = new WebSocket("ws://" + location.host + "/ws");
            ws.onmessage = function(event) {
                let messages = JSON.parse(event.data);
                let container = document.getElementById("pending-list");
                container.innerHTML = "";
                messages.forEach(function(msg) {
                    let div = document.createElement("div");
                    div.style.border = "1px solid #ccc";
                    div.style.padding = "5px";
                    div.style.margin = "5px";
                    div.innerHTML = `
                        <b>${msg.user_name}</b> (${msg.persona})<br>
                        <p>${msg.content.substring(0, 200)}...</p>
                        <small>Tokens: ${JSON.stringify(msg.token_usage)}</small><br>
                        <button onclick="sendMsg('${msg.uid}')">Send Now</button>
                        <button onclick="discardMsg('${msg.uid}')">Discard</button>
                        <button onclick="holdMsg('${msg.uid}')">Hold</button>
                        <span id="edit-${msg.uid}" style="display:none">
                            <textarea id="edit-text-${msg.uid}" rows="3" cols="50">${msg.content}</textarea>
                            <button onclick="submitEdit('${msg.uid}')">Submit Edited (new 10s window)</button>
                        </span>
                    `;
                    if(msg.held) {
                        div.querySelector(`#edit-${msg.uid}`).style.display = "block";
                    }
                    container.appendChild(div);
                });
            };

            function sendMsg(uid) { fetch('/action/send?msg_id='+uid, {method:'POST'}); }
            function discardMsg(uid) { fetch('/action/discard?msg_id='+uid, {method:'POST'}); }
            function holdMsg(uid) { fetch('/action/hold?msg_id='+uid, {method:'POST'}); }
            function submitEdit(uid) {
                let newText = document.getElementById('edit-text-'+uid).value;
                fetch('/action/submit_edit', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({msg_id: uid, new_content: newText})
                });
            }
        </script>
    </head>
    <body>
        <h1>Pending Messages</h1>
        <div id="pending-list"></div>
    </body>
    </html>
    """