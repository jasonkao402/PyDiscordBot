from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from discord import Interaction, Message, Webhook, app_commands
from wcwidth import wcswidth

from config_loader import config_toml

if TYPE_CHECKING:
    from discord.abc import Messageable

TWTZ = timezone(timedelta(hours=8))

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

async def long_message_splitter(_ch: Messageable | Webhook, text: str, title: str = "", chunk_size: int = 1900) -> Message:
    """Split a long message into chunks that fit within Discord's message limits and send them sequentially."""

    last_message: Message | None = None

    if len(text) > chunk_size:
        parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        len_parts = len(parts)
        for i, part in enumerate(parts):
            last_message = await _ch.send(f"# {title} part {i + 1}/{len_parts}\n{part}")
    else:
        last_message = await _ch.send(f"# {title}\n{text}")

    if last_message is None:
        msg = "Failed to send message chunk"
        raise RuntimeError(msg)

    return last_message

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
