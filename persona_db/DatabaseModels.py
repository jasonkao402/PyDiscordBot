from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set
import json

class PersonaVisibility(Enum):
    PRIVATE = 0
    PUBLIC = 1

    def __str__(self):
        return self.name

@dataclass
class Persona:
    uid: int
    persona_name: str
    content: str
    owner_uid: int
    # visibility: PersonaVisibility
    is_public: bool
    allowed_role_ids: Set[int]
    created_at: str
    updated_at: str
    last_interaction_recv_at: Optional[str] = None
    interaction_count: int = 0 # unused for now

    def permission_full(self, user_id: int, user_role_ids: Set[int] = set()) -> bool:
        if self.owner_uid == user_id:
            return True
        return any(role_id in self.allowed_role_ids for role_id in user_role_ids)

    def permission_basic(self, user_id: int, user_role_ids: Set[int] = set()) -> bool:
        if self.is_public:
            return True
        return self.permission_full(user_id, user_role_ids)
    
    def __str__(self):
        return f"Persona(uid={self.uid:3d}, persona={self.persona_name}, owner_uid={self.owner_uid}, is_public={self.is_public})"

@dataclass
class PersonaPartial:
    uid: int
    persona_name: str
    owner_uid: int
    is_public: bool

    def __str__(self):
        return f"PersonaPartial(uid={self.uid:3d}, persona={self.persona_name}, owner_uid={self.owner_uid}, is_public={self.is_public})"

@dataclass
class DiscordUser:
    user_uid: int
    selected_persona_uid: int
    last_interaction_send_at: Optional[str] = None
    interaction_count: int = 0 # unused for now
    last_payout_at: Optional[str] = None
    balance: int = 0

    def __str__(self):
        return f"DiscordUser(user_uid={self.user_uid}, selected_persona_uid={self.selected_persona_uid}, balance={self.balance})"

    def set_balance(self, amount: int):
        self.balance = amount

    def adjust_balance(self, delta: int):
        if self.balance + delta < 0:
            raise ValueError("Insufficient balance")
        self.balance += delta

@dataclass
class ChatInteraction:
    msg_uid: int #PK
    user_uid: int #FK
    persona_uid: int #FK
    created_at: str
    is_memorized: bool = False
    main_content: str = ""
    summary: Optional[str] = None
    
@dataclass
class PersonaMemories:
    memory_uid: int #PK
    memory_content: str
    persona_uid: int #FK
    source_msg_uids: str # comma-separated list of msg_uids that contributed to this memory
    created_at: str
    updated_at: str