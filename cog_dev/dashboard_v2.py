from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse
from jinja2 import Template
import asyncio
import json
import time

app = FastAPI()

# Queue to hold requests
request_queue = []

# HTML template for the UI
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proxy API</title>
</head>
<body>
    <h2>Proxy API Request Queue</h2>
    <form action="/send_request" method="post">
        <label for="data">Request Data:</label>
        <input type="text" id="data" name="data" required>
        <button type="submit">Send</button>
    </form>

    <h3>Queued Requests:</h3>
    <ul>
        {% for request in request_queue %}
            <li>{{ request }}</li>
        {% endfor %}
    </ul>

    <form action="/send_all" method="post">
        <button type="submit">Send All Queued Requests</button>
    </form>

    <form action="/send_immediate" method="post">
        <button type="submit">Send Immediate Request</button>
    </form>
</body>
</html>
"""

# Render the HTML page with current queue
@app.get("/", response_class=HTMLResponse)
async def read_root():
    template = Template(html_template)
    rendered_html = template.render(request_queue=request_queue)
    return HTMLResponse(content=rendered_html)

# Endpoint to queue a request
@app.post("/send_request")
async def queue_request(data: str = Form(...)):
    request_queue.append({"data": data, "time": time.time()})
    return {"message": "Request queued"}

# Function to send a request after a delay
async def send_after_delay(data: str):
    await asyncio.sleep(10)  # 10 second delay
    # Simulate forwarding the request (e.g., to an external service)
    return {"response": f"Response for {data}"}

# Endpoint to send the queued requests after a delay
@app.post("/send_all")
async def send_all():
    results = []
    for req in request_queue:
        result = await send_after_delay(req["data"])
        results.append(result)
    request_queue.clear()  # Clear the queue after sending
    return {"results": results}

# Endpoint to send the next request immediately
@app.post("/send_immediate")
async def send_immediate():
    if request_queue:
        req = request_queue.pop(0)
        result = await send_after_delay(req["data"])
        return {"result": result}
    return {"error": "No requests in the queue"}

# Entry Point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_v2:app", host="127.0.0.1", port=8000, reload=True)