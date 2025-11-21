from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, Enum as SAEnum,
    DateTime, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# =========================
# ENUM (mapped to INTEGER like SQLite)
# =========================
class PersonaVisibility(Enum):
    PRIVATE = 0
    PUBLIC = 1


# =========================
# Persona Table
# =========================
class Persona(Base):
    __tablename__ = "personas"

    uid = Column(Integer, primary_key=True, autoincrement=True)
    persona = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    owner_uid = Column(Integer, nullable=False)
    visibility = Column(SAEnum(PersonaVisibility), nullable=False)

    created_at = Column(String, nullable=False)  # Keep ISO string for SQLite compatibility
    updated_at = Column(String, nullable=False)
    last_interaction_recv_at = Column(String, nullable=False)

    interaction_count = Column(Integer, default=0)

    # Relationship: One Persona has many interactions
    interactions = relationship(
        "UserPersonaInteraction", back_populates="persona", cascade="all, delete-orphan"
    )

    def permission_check(self, user_uid: int) -> bool:
        return bool(
            self.visibility == PersonaVisibility.PUBLIC
            or self.owner_uid == user_uid
        )


# =========================
# Discord User Table
# =========================
class DiscordUser(Base):
    __tablename__ = "discord_user"

    user_uid = Column(Integer, primary_key=True)

    selected_persona_uid = Column(
        Integer,
        ForeignKey("personas.uid", ondelete="SET NULL"),
        nullable=True
    )
    last_interaction_send_at = Column(String, nullable=True)
    interaction_count = Column(Integer, default=0)

    selected_persona = relationship("Persona")
    interactions = relationship(
        "UserPersonaInteraction",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# =========================
# User-Persona Interaction Table (Composite PK)
# =========================
class UserPersonaInteraction(Base):
    __tablename__ = "user_persona_interactions"

    user_uid = Column(
        Integer,
        ForeignKey("discord_user.user_uid", ondelete="CASCADE"),
        primary_key=True,
    )
    persona_uid = Column(
        Integer,
        ForeignKey("personas.uid", ondelete="CASCADE"),
        primary_key=True,
    )

    interaction_count = Column(Integer, default=1)
    last_interaction_at = Column(String, nullable=False)

    # Relationship references
    user = relationship("DiscordUser", back_populates="interactions")
    persona = relationship("Persona", back_populates="interactions")
