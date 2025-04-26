import requests
import time

# URL of the proxy API
url = "http://localhost:8000/"

def send_request(data):
    response = requests.post(f"{url}send_request", data={"data": data})
    return response.json()

def send_immediate():
    response = requests.post(f"{url}send_immediate")
    return response.json()

def send_all():
    response = requests.post(f"{url}send_all")
    return response.json()

def test_proxy():
    # Sending several requests to be queued
    print("Sending requests to the queue...")
    for i in range(5):
        response = send_request(f"Request {i+1}")
        print(f"Queued: {response}")

    # Simulating the immediate sending of the first request
    print("\nSending immediate request...")
    immediate_response = send_immediate()
    print(f"Immediate response: {immediate_response}")

    # Waiting 10 seconds to send all queued requests
    print("\nWaiting for 10 seconds to send queued requests...")
    time.sleep(10)
    all_response = send_all()
    print(f"All queued responses: {all_response}")

if __name__ == "__main__":
    test_proxy()
