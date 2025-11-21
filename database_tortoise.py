from unittest import result
from tortoise import Tortoise, run_async
from cog.archive.database_base import Persona, PersonaVisibility, DiscordUser, UserPersonaInteraction
from typing import Optional, List
from datetime import datetime
from tortoise.expressions import F

class PersonaDatabase:

    async def init(self, db_path="sqlite://llm_character_cards.db"):
        await Tortoise.init(
            db_url=db_path,
            modules={"models": ["cog_dev.database_base"]},
        )
        await Tortoise.generate_schemas()

    # ----------------------------
    # CRUD
    # ----------------------------
    async def create_persona(self, p_name, p_content, owner_uid, visibility):
        # limit check
        count = await Persona.filter(owner_uid=owner_uid).count()
        if count >= 5:
            print(f"User {owner_uid} reached persona limit.")
            return None

        p = await Persona.create(
            persona=p_name,
            content=p_content,
            owner_uid=owner_uid,
            visibility=visibility,
            last_interaction_recv_at=datetime.now(),
        )
        return p

    async def get_persona(self, persona_uid: int, user_uid: int) -> Optional[Persona]:
        persona = await Persona.filter(uid=persona_uid).first()
        if persona and persona.permission_check(user_uid):
            return persona
        return None

    async def get_persona_no_check(self, persona_uid: int):
        return await Persona.filter(p_uid=persona_uid).first()

    async def update_persona(self, persona_uid: int, user_uid: int, **updates) -> bool:
        persona = await Persona.filter(uid=persona_uid, owner_uid=user_uid).first()
        if not persona:
            return False

        for k, v in updates.items():
            setattr(persona, k, v)

        persona.updated_at = datetime.now()
        await persona.save()
        return True

    async def delete_persona(self, persona_uid: int, user_uid: int) -> bool:
        # Clear user selections
        await DiscordUser.filter(selected_persona_uid=persona_uid).update(
            selected_persona_uid=-1
        )

        # Delete persona
        deleted_count = await Persona.filter(uid=persona_uid, owner_uid=user_uid).delete()
        return deleted_count > 0

    async def list_personas(self, user_uid: int) -> List[Persona]:
        return await Persona.filter(owner_uid=user_uid).all()

    # ----------------------------
    # selection
    # ----------------------------
    async def set_selected_persona(self, user_uid: int, persona_uid: int) -> bool:
        _persona = await self.get_persona(persona_uid, user_uid)
        if not _persona:
            return False

        await DiscordUser.update_or_create(
            defaults={"selected_persona_uid": _persona}, user_uid=user_uid
        )
        return True

    async def get_selected_persona(self, user_uid: int) -> Optional[Persona]:
        user = await DiscordUser.filter(user_uid=user_uid).first()
        if user and user.selected_persona_uid_id:  # Use `_id` to get the raw integer value
            _persona = await Persona.filter(uid=user.selected_persona_uid_id).first()
            return _persona
        return None

    async def get_selected_persona_uid(self, user_uid: int) -> int:
        user = await DiscordUser.filter(user_uid=user_uid).first()
        if user and user.selected_persona_uid:
            return user.selected_persona_uid
        return -1

    async def clear_selected_persona(self, user_uid: int):
        await DiscordUser.filter(user_uid=user_uid).update(selected_persona_uid=None)

    # ----------------------------
    # interactions
    # ----------------------------
    async def increment_interaction_count(self, persona_uid: int, user_uid: int):
        now = datetime.now()

        # Persona
        await Persona.filter(uid=persona_uid).update(
            total_recv_interaction_count=F("total_recv_interaction_count") + 1,
            last_interaction_recv_at=now,
        )

        # DiscordUser (global)
        await DiscordUser.update_or_create(
            defaults={
                "total_send_interaction_count": F("total_send_interaction_count") + 1,
                "last_interaction_send_at": now,
            },
            user_uid=user_uid,
        )

        # User-Persona interaction
        interaction, created = await UserPersonaInteraction.get_or_create(
            user_uid=user_uid, persona_uid=persona_uid
        )
        interaction.interaction_count += 1
        interaction.last_interaction_at = now
        await interaction.save()

    # ----------------------------
    # Stats
    # ----------------------------
    # async def get_user_interaction_stats(self, user_uid: int):
    #     total = (
    #         await UserPersonaInteraction.filter(user_uid=user_uid)
    #         .all()
    #         .values_list("interaction_count", flat=True)
    #     )

    #     if not total:
    #         return None

    #     for i in range(len(total)):
    #         total[i] = int(total[i])
    #     total_interactions = sum(total)

    #     # Most interacted persona
    #     top = (
    #         await UserPersonaInteraction.filter(user_uid=user_uid)
    #         .order_by("-interaction_count")
    #         .first()
    #     )

    #     if not top:
    #         return {
    #             "total_interactions": total_interactions,
    #             "most_interacted_persona_uid": None,
    #             "most_interacted_persona_name": None,
    #             "most_interacted_count": 0,
    #         }

    #     persona = await Persona.filter(uid=top.persona_uid).first()

    #     return {
    #         "total_interactions": total_interactions,
    #         "most_interacted_persona_uid": persona.uid,
    #         "most_interacted_persona_name": persona.persona,
    #         "most_interacted_count": top.interaction_count,
    #     }

    # async def get_top_users(self, limit=5):
    #     return (
    #         await DiscordUser.all()
    #         .order_by("-interaction_count")
    #         .limit(limit)
    #         .values("user_uid", "interaction_count")
    #     )

async def main():
    manager = PersonaDatabase()
    await manager.init()

    user1_uid = 999999
    user2_uid = 225833749156331520

    # Cleanup for fresh run (optional)
    await Persona.all().delete()
    # await DiscordUser.all().delete()

    print("--- Creating Personas ---")
    p1 = await manager.create_persona("My Private Persona", "Hidden", user1_uid, PersonaVisibility.PRIVATE)
    p2 = await manager.create_persona("Public Hero", "Saves the day", user1_uid, PersonaVisibility.PUBLIC)
    
    if p1:
        print(f"Created: {p1}")
    if p2:
        print(f"Created: {p2}")

    print("\n--- Selecting Persona ---")
    if p2:
        result = await manager.set_selected_persona(user1_uid, p2.uid)
        print(f"Selection result: {result}")
        selected = await manager.get_selected_persona(user1_uid)
        if selected:
            print(f"User {user1_uid} Selected: {selected.persona}")
        else:
            print("No persona selected.")

    print("\n--- Listing Personas for User 2 ---")
    # User 2 should only see Public Hero, not My Private Persona
    personas_u2 = await manager.list_personas(user2_uid)
    for p in personas_u2:
        print(f"Visible to U2: {p.persona} (Visibility: {p.visibility})")

    print("\n--- Simulating Interactions ---")
    if p2:
        await manager.increment_interaction_count(p2.uid, user1_uid)
        await manager.increment_interaction_count(p2.uid, user1_uid)
        print("Interactions incremented.")

    print("\n--- Stats ---")
    # stats = await manager.get_user_interaction_stats(user1_uid)
    # print(f"User 1 Stats: {stats}")

    # await manager.

if __name__ == "__main__":
    run_async(main())