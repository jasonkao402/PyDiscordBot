# moderation.py
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
import discord
from discord import Message
from enum import Enum

class ModerationAction(Enum):
    DEFAULT = "default"  # auto‑send after window if no action taken
    HOLD = "hold"
    DISCARD = "discard"
    SEND_IMMEDIATELY = "send_immediately"
    
@dataclass
class PendingMessage:
    uid: str               # unique id
    content: str           # LLM reply text
    received_at: float     # timestamp (monotonic or Unix)
    user_id: int           # Discord user id
    display_name: str      # for display
    channel_ctx: Message   # where to send
    token_usage: dict      # {prompt_tokens, completion_tokens, total}
    persona_name: str      # for display
    # internal state
    stateAction: ModerationAction = field(default=ModerationAction.DEFAULT)  # default to auto‑send after window
    edited_content: Optional[str] = None
    timer_task: Optional[asyncio.Task] = None

class PendingMessageManager:
    def __init__(self, send_callback: Callable[[PendingMessage], Awaitable[None]]):
        self.queue: list[PendingMessage] = []   # simple FIFO; could be asyncio.Queue
        self.send_callback = send_callback       # async function to actually send to Discord
        self.window = 10                        # default seconds, adjustable
        self._lock = asyncio.Lock()
        
    async def add(self, msg: PendingMessage):
        async with self._lock:
            self.queue.append(msg)
        # start auto‑send timer
        msg.timer_task = asyncio.create_task(self._auto_send_after(msg, self.window))

    async def _auto_send_after(self, msg: PendingMessage, delay: float):
        try:
            await asyncio.sleep(delay)
            # If not held, send automatically
            if msg.stateAction == ModerationAction.DEFAULT and msg in self.queue:
                async with self._lock:
                    await self.send_callback(msg)
                    if msg in self.queue:
                        self.queue.remove(msg)
        except asyncio.CancelledError:
            pass   # timer was cancelled by an explicit action

    async def send_immediately(self, msg_id: str):
        msg = await self._pop(msg_id)
        if msg and msg.stateAction == ModerationAction.SEND_IMMEDIATELY:
            # If held, allow sending of the (possibly edited) content
            if msg.edited_content:
                msg.content = msg.edited_content
        if msg:
            await self.send_callback(msg)

    async def discard(self, msg_id: str):
        msg = await self._pop(msg_id)
        if msg and msg.timer_task:
            msg.stateAction = ModerationAction.DISCARD
            msg.timer_task.cancel()

    async def hold(self, msg_id: str):
        msg = await self._get(msg_id)
        if msg:
            msg.stateAction = ModerationAction.HOLD
            if msg.timer_task:
                msg.timer_task.cancel()   # disable auto‑send
            # The message remains in queue until admin sends the edited version

    async def submit_edited(self, msg_id: str, new_content: str):
        """Called when admin finishes editing and wants to re‑submit."""
        msg = await self._get(msg_id)
        if msg and msg.stateAction == ModerationAction.HOLD:
            msg.edited_content = new_content
            # Treat as fresh incoming – start a new 10‑s window
            msg.stateAction = ModerationAction.DEFAULT   # auto‑send after new window
            msg.timer_task = asyncio.create_task(self._auto_send_after(msg, self.window))
            # Optionally update received_at to now? The spec doesn't require, but fine.
            msg.received_at = time.monotonic()

    async def _pop(self, msg_id: str) -> Optional[PendingMessage]:
        async with self._lock:
            for i, m in enumerate(self.queue):
                if m.uid == msg_id:
                    return self.queue.pop(i)
        return None

    async def _get(self, msg_id: str) -> Optional[PendingMessage]:
        async with self._lock:
            for m in self.queue:
                if m.uid == msg_id:
                    return m
        return None

    def get_all(self) -> list[PendingMessage]:
        # For webUI – return a snapshot (no lock needed for reads if only appending/removing)
        return list(self.queue)