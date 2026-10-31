from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from discord import Interaction, Message, Webhook, app_commands, WebhookMessage
from wcwidth import wcswidth

from config_loader import config_toml

if TYPE_CHECKING:
    from discord.abc import Messageable

TWTZ = timezone(timedelta(hours=8))
DISCORD_LIMIT = 2000
TITLE_LIMIT = 50

def clamp(n: float, minn: float = 0, maxn: float = 100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def is_admin_check():
    ''' Check if the user is in the admin list from config_toml. Use as a decorator for commands.'''
    def predicate(interaction: Interaction) -> bool:
        return int(interaction.user.id) in config_toml.get('auth', {}).get('admin_list', [])
    return app_commands.check(predicate)

def dev_check(uid: int) -> bool:
    return int(uid) in config_toml.get('auth', {}).get('admin_list', [])

# def sepLines(itr: Iterable, sep: str = '\n'):
#     return sep.join(itr)

# def utc_format(t: datetime):
#     return t.replace(tzinfo=UTC).astimezone(TWTZ).strftime("%Y-%m-%d %H:%M:%S")

def wcformat(s: str, w: int = 12, align_left: bool = True):
    if align_left:
        return (s + ' ' * (w - wcswidth(s)))
    return (' ' * (w - wcswidth(s)) + s)

# def multiChk(s: str, l: list) -> int:
#     for i in l:
#         if i in s: return i
#     return -1

# def cosineSim(a, b) -> float:
#     return dot(a, b) / (norm(a) * norm(b))

# def simRank(a, b, K=3) -> tuple:
#     sim = array([cosineSim(a, vector) for vector in b])
#     idx = argsort(sim)[:-K - 1:-1]
#     return idx, sim[idx]

 
 
def _chunks(text: str, limit: int) -> list[str]:
    """Split on line boundaries; hard-wrap only lines that are longer than `limit`."""
    chunks: list[str] = []
    buf = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:  # a single oversized line
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) > limit:
            chunks.append(buf)
            buf = ""
        buf += line
    if buf:
        chunks.append(buf)
    return chunks or [""]
 
 
async def long_message_splitter(
    target: Interaction | Messageable | Webhook,
    text: str,
    title: str = "",
    chunk_size: int = 1900,
    *,
    ephemeral: bool = False,
) -> Message | WebhookMessage:
    """Send `text` in several messages, each within Discord's 2000-character limit.
 
    `target` can be:
      * an Interaction  -> first chunk uses response.send_message (or followup if you
                           already deferred/responded); the rest use followup.send
      * a Messageable   -> channel.send
      * a Webhook       -> webhook.send(wait=True)
    `ephemeral` only applies to Interactions.
    """
    title = title[:TITLE_LIMIT]
    header_room = len(f"# {title} part 99/99\n")  # keep header + chunk under 2000
    limit = max(100, min(chunk_size, DISCORD_LIMIT - header_room))
    parts = _chunks(text, limit)
    total = len(parts)
 
    async def _send(content: str) -> Message | WebhookMessage:
        if isinstance(target, Interaction):
            if not target.response.is_done():
                await target.response.send_message(content, ephemeral=ephemeral)
                return await target.original_response()
            return await target.followup.send(content, ephemeral=ephemeral, wait=True)
        if isinstance(target, Webhook):
            return await target.send(content, wait=True)
        return await target.send(content)
 
    last: Message | WebhookMessage | None = None
    for i, part in enumerate(parts, start=1):
        header = f"# {title} part {i}/{total}\n" if total > 1 else f"# {title}\n"
        last = await _send(header + part)
 
    if last is None:  # unreachable: _chunks always returns at least one element
        msg = "Failed to send message chunk"
        raise RuntimeError(msg)
    return last

@dataclass
class UserDict:
    uid: int
    name: str
    preferred_name: str | None = None
    descr: str | None = None

    @property
    def effective_name(self):
        # Priority: preferred_name > display_name > name
        return self.preferred_name or self.name

    # discord name regex = ^[a-z0-9._]{2,32}$
    # openai api role name regex = ^[a-zA-Z0-9_-]{1,64}$
    @property
    def role_name(self):
        return self.name.replace('.', '_')

class PlaceholderReplacer:
    def __init__(self, _user_dict: UserDict):
        self.user_dict = _user_dict
        self.converters = {
            "user": lambda: self.user_dict.effective_name,
            "descr": lambda: self.user_dict.descr or "",
            "time": lambda: datetime.now(TWTZ).strftime("%Y/%m/%d %H:%M %a"),
        }

    # 支援 Unicode（包含中文、日文、數字、底線）
    def replace_placeholders(self, text: str) -> str:
        PLACEHOLDER_PATTERN = re.compile(r"\\?\{\{([\w]+)\}\}", re.UNICODE)

        def replacer(match: re.Match) -> str:
            full = match.group(0)
            var = match.group(1)
            if full.startswith("\\"):
                return f"{{{{{var}}}}}"   # 輸出 {{var}}
            if var in self.converters:
                return str(self.converters[var]())
            return full   # 未知變數保留原樣

        return PLACEHOLDER_PATTERN.sub(replacer, text)


# testing
# if __name__ == "__main__":
#     d = {"a": 1, "b": 2, "c": 3}
#     print(sepLines([f"{k}: {v}" for k, v in d.items()]))
