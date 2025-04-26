from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
import aiohttp
import time
from typing import List, Dict
import uuid
from starlette.websockets import WebSocketDisconnect

app = FastAPI()

# In-memory queue to store requests
request_queue: List[Dict] = []
# WebSocket connections for dashboard updates
connected_clients: List[WebSocket] = []

# Request model
class ProxyRequest(BaseModel):
    url: str
    payload: dict

# HTML for the dashboard
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Proxy API Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        button { padding: 10px 20px; margin: 10px 0; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
        button:hover { background-color: #45a049; }
    </style>
</head>
<body>
    <h1>Proxy API Dashboard</h1>
    <button onclick="sendNow()">Send All Now</button>
    <table id="requestTable">
        <tr>
            <th>Request ID</th>
            <th>Received Time</th>
            <th>Status</th>
            <th>Response</th>
        </tr>
    </table>
    <script>
        const ws = new WebSocket("ws://" + window.location.host + "/ws");
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            updateTable(data);
        };

        function updateTable(requests) {
            const table = document.getElementById("requestTable");
            // Clear table except header
            while (table.rows.length > 1) table.deleteRow(1);
            // Add rows
            requests.forEach(req => {
                const row = table.insertRow();
                row.insertCell().textContent = req.id;
                row.insertCell().textContent = new Date(req.received_time * 1000).toLocaleString();
                row.insertCell().textContent = req.status;
                row.insertCell().textContent = req.response || "";
            });
        }

        async function sendNow() {
            await fetch("/send", { method: "POST" });
            alert("Sent all queued requests!");
        }
    </script>
</body>
</html>
"""

@app.get("/")
async def get_dashboard():
    return HTMLResponse(dashboard_html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Send initial queue state
        await websocket.send_json(request_queue)
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

async def broadcast_queue():
    # Broadcast queue updates to all connected clients
    for client in connected_clients:
        try:
            await client.send_json(request_queue)
        except:
            connected_clients.remove(client)

@app.post("/proxy")
async def queue_request(request: ProxyRequest):
    # Add request to queue
    request_id = str(uuid.uuid4())
    received_time = time.time()
    queue_entry = {
        "id": request_id,
        "url": request.url,
        "payload": request.payload,
        "received_time": received_time,
        "status": "Queued",
        "response": None
    }
    request_queue.append(queue_entry)
    await broadcast_queue()
    return {"request_id": request_id}

@app.post("/send")
async def send_now():
    # Process all queued requests immediately
    tasks = [process_request(req) for req in request_queue]
    await asyncio.gather(*tasks)
    return {"status": "All requests sent"}

async def process_request(queue_entry: Dict):
    # Skip if already processed
    if queue_entry["status"] != "Queued":
        return
    queue_entry["status"] = "Processing"
    await broadcast_queue()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(queue_entry["url"], json=queue_entry["payload"]) as resp:
                response_text = await resp.text()
                queue_entry["status"] = "Completed"
                queue_entry["response"] = response_text[:100]  # Truncate for display
        except Exception as e:
            queue_entry["status"] = "Failed"
            queue_entry["response"] = str(e)
    await broadcast_queue()

@app.on_event("startup")
async def startup_event():
    # Background task to process queue
    async def queue_processor():
        while True:
            if request_queue:
                current_time = time.time()
                # Process requests older than 10 seconds
                for req in request_queue:
                    if req["status"] == "Queued" and (current_time - req["received_time"]) >= 10:
                        await process_request(req)
            await asyncio.sleep(1)
    asyncio.create_task(queue_processor())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)