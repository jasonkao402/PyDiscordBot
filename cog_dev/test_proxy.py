import requests
import time
import json

# API endpoint
PROXY_URL = "http://localhost:8000/proxy"

# Sample requests
requests_to_send = [
    {
        "url": "http://example.com",
        "payload": {"message": "Hello, this is request 1!"}
    },
    {
        "url": "http://example.com",
        "payload": {"message": "Hi there, request 2 here!"}
    },
    {
        "url": "http://example.com",
        "payload": {"message": "Yo, request 3 checking in!"}
    }
]

def send_request(req):
    response = requests.post(PROXY_URL, json=req)
    if response.status_code == 200:
        return response.json()["request_id"]
    else:
        return None

def main():
    print("Sending requests to proxy API...")
    request_ids = []
    
    # Send all requests
    for i, req in enumerate(requests_to_send, 1):
        request_id = send_request(req)
        if request_id:
            print(f"Request {i} sent with ID: {request_id}")
            request_ids.append(request_id)
        else:
            print(f"Failed to send request {i}")
    
    print("\nWaiting for responses (10 seconds unless 'Send' is pressed in dashboard)...")
    # Note: In a real scenario, we'd poll the API for status or use WebSocket.
    # For simplicity, we wait 12 seconds to ensure responses are processed.
    time.sleep(12)
    
    print("\nResponses should have been processed. Check dashboard for details.")
    # Optionally, add an endpoint in the API to fetch response status by ID
    # For this demo, we assume responses are visible in the dashboard

if __name__ == "__main__":
    main()