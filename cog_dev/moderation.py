# moderation.py
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

TIME_WINDOW = 6.0  # seconds for auto-send after message is added to moderation queueq
class ActionState(IntEnum):
    DEFAULT = 0     # default state, will auto-send after window
    COMPLETED = 1   # already sent (either auto or manually)
    HOLD = 2        # held by admin, waiting for edited content
    REJECTED = 3    # rejected by admin, will not send

@dataclass
class TrimedResponse:
    response_text: str
    timestamp: int
    thinking_content: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    _code: int = 0

    def __str__(self):
        return f"Response:\n{self.response_text}\nThinking:\n{self.thinking_content}\nTokens:\n{' '.join(f'{k}: {v}' for k, v in self.token_usage.items())}"

@dataclass
class PendingMessage:
    uid: str
    user_id: int
    user_display_name: str
    input_msg: str
    content: str
    _received_at: float = field(default_factory=time.monotonic, init=False)
    _ttl: float = field(default=10.0, init=False)
    _action_state: ActionState = field(default=ActionState.DEFAULT, init=False)
    _timer_task: asyncio.Task | None = field(default=None, init=False)
    future: asyncio.Future = field(init=False)

    def __post_init__(self):
        self.future = asyncio.get_running_loop().create_future()

    def to_dict(self):
        return {
            "uid": self.uid,
            "user_id": self.user_id,
            "user_display_name": self.user_display_name,
            "input_msg": self.input_msg,
            "content": self.content,
            "received_at": self._received_at,
            "ttl": self._ttl,
            "actionState": self._action_state.value,
        }

class PendingMessageManager:
    def __init__(self, update_callback: Callable[[], Awaitable[None]] | None = None):
        self.queue: list[PendingMessage] = []   # simple FIFO; could be asyncio.Queue
        self.update_callback = update_callback
        self.window = TIME_WINDOW                        # default seconds, adjustable
        self._lock = asyncio.Lock()

    async def moderate(self, msg: PendingMessage) -> PendingMessage:
        async with self._lock:
            self.queue.append(msg)
        # start auto‑send timer
        print(f"Added message {msg.uid[:8]} to moderation queue. Starting auto-send timer.")
        msg._received_at = time.monotonic()
        msg._ttl = self.window
        msg._action_state = ActionState.DEFAULT
        msg._timer_task = asyncio.create_task(self.auto_send_after(msg, self.window))
        if self.update_callback:
            await self.update_callback()

        await msg.future
        return msg

    async def auto_send_after(self, msg: PendingMessage, delay: float):
        await asyncio.sleep(delay)
        try:
            # If not held, send automatically
            if msg._action_state == ActionState.DEFAULT and msg in self.queue:
                async with self._lock:
                    if msg in self.queue:
                        self.queue.remove(msg)
                msg._action_state = ActionState.COMPLETED
                if not msg.future.done():
                    msg.future.set_result(msg)
                if self.update_callback:
                    await self.update_callback()
        except asyncio.CancelledError:
            pass   # timer was cancelled by an explicit action

    async def send_immediately(self, msg_id: str):
        msg = await self._pop(msg_id)
        if msg:
            msg._action_state = ActionState.COMPLETED
            if not msg.future.done():
                msg.future.set_result(msg)
            if self.update_callback:
                await self.update_callback()

    async def reject(self, msg_id: str):
        msg = await self._pop(msg_id)
        if msg:
            if msg._timer_task:
                msg._timer_task.cancel()
            msg._action_state = ActionState.REJECTED
            msg.content = "[REJECTED] " + msg.content  # Optionally modify content to indicate rejection
            if not msg.future.done():
                msg.future.set_result(msg)
            if self.update_callback:
                await self.update_callback()

    async def hold(self, msg_id: str):
        msg = await self._get(msg_id)
        if msg:
            msg._action_state = ActionState.HOLD
            if msg._timer_task:
                msg._timer_task.cancel()   # disable auto‑send
            # The message remains in queue until admin sends the edited version
            if self.update_callback:
                await self.update_callback()

    async def submit_edited(self, msg_id: str, new_content: str):
        """Called when admin finishes editing and wants to re‑submit."""
        msg = await self._pop(msg_id)
        if msg:
            msg.content = new_content
            msg._received_at = time.monotonic()
            msg._ttl = self.window
            msg._action_state = ActionState.DEFAULT
            msg._timer_task = asyncio.create_task(self.auto_send_after(msg, self.window))
            async with self._lock:
                self.queue.append(msg)
            if self.update_callback:
                await self.update_callback()

    async def _pop(self, msg_id: str) -> PendingMessage | None:
        async with self._lock:
            for i, m in enumerate(self.queue):
                if m.uid == msg_id:
                    return self.queue.pop(i)
        return None

    async def _get(self, msg_id: str) -> PendingMessage | None:
        async with self._lock:
            for m in self.queue:
                if m.uid == msg_id:
                    return m
        return None

    def get_all(self) -> list[PendingMessage]:
        # For webUI – return a snapshot (no lock needed for reads if only appending/removing)
        return list(self.queue)
