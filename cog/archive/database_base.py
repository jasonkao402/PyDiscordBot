from tortoise import fields, models
from enum import IntEnum


class PersonaVisibility(IntEnum):
    PRIVATE = 0
    PUBLIC = 1


class Persona(models.Model):
    uid = fields.IntField(primary_key=True)
    persona = fields.CharField(max_length=255)
    content = fields.TextField()
    owner_uid = fields.BigIntField()
    visibility = fields.IntEnumField(PersonaVisibility)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    last_interaction_recv_at = fields.DatetimeField(null=True)
    total_recv_interaction_count = fields.IntField(default=0)
    
    class Meta:
        table = "personas"
        
    def permission_check(self, user_uid: int) -> bool:
        return self.visibility == PersonaVisibility.PUBLIC or self.owner_uid == user_uid

    def __str__(self):
        return f"Persona(uid={self.uid}, persona={self.persona}, owner={self.owner_uid}, vis={self.visibility.name})"


class DiscordUser(models.Model):
    user_uid = fields.BigIntField(primary_key=True)
    selected_persona_uid = fields.ForeignKeyField(
        "models.Persona", null=False, default=-1
    )
    last_interaction_send_at = fields.DatetimeField(null=True)
    total_send_interaction_count = fields.IntField(default=0)
    
    class Meta:
        table = "discord_user"


class UserPersonaInteraction(models.Model):
    user_uid = fields.BigIntField()
    persona_uid = fields.IntField()

    interaction_count = fields.IntField(default=1)
    last_interaction_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_persona_interactions"
        unique_together = ("user_uid", "persona_uid")
