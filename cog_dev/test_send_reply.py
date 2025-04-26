import asyncio
import httpx

API_BASE = "http://127.0.0.1:8000"
session_ids = ["user1", "user2", "user3"]  # 模擬三個 session
replies = [
    "Hello! How can I assist you today?",
    "Sure, your order is on the way!",
    "Please let me know if you have any further questions."
]

async def send_fake_reply(session_id, reply):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/send_reply/{session_id}",
            json={"reply": reply}
        )
        if response.status_code == 200:
            print(f"✅ Sent reply to session {session_id}: {reply}")
        else:
            print(f"❌ Failed to send reply to session {session_id}: {response.text}")

async def main():
    tasks = []
    for session_id, reply in zip(session_ids, replies):
        tasks.append(send_fake_reply(session_id, reply))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
