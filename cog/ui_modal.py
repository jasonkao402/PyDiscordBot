from discord.ui import Modal, TextInput, Select
from discord import Color, Interaction, Message, TextStyle, SelectOption

def _parse_allowed_set(allowed_role_ids: str) -> set[int]:
    return set(int(role_id.strip()) for role_id in allowed_role_ids.split(",") if role_id.strip())

class BasePersonaModal(Modal):
    def __init__(self, title: str, callback, persona_name: str = "", content: str = "", is_public: bool = True, allowed_role_ids: set[int] = set()):
        super().__init__(title=title)
        self.callback = callback

        # Add fields to the modal
        self._name_input = TextInput(label="Persona Name", default=persona_name, placeholder="Enter persona name", required=True)
        self._content_input = TextInput(label="Content", default=content, placeholder="Enter persona content", style=TextStyle.paragraph, required=True)
        options = [
            SelectOption(label="Public", value="public", default=is_public),
            SelectOption(label="Private", value="private", default=not is_public)
        ]
        allowed_role_ids_str = ",".join(str(role_id) for role_id in allowed_role_ids)
        self._is_public_input = Select(placeholder="Select visibility", options=options, min_values=1, max_values=1)
        self._allowed_role_ids = TextInput(label="Allowed Role IDs (comma-separated)", default=allowed_role_ids_str, placeholder="Enter role IDs that can access this persona, separated by commas", required=False)
        self.add_item(self._name_input)
        self.add_item(self._content_input)
        self.add_item(self._is_public_input)
        self.add_item(self._allowed_role_ids)

    async def on_submit(self, interaction: Interaction):
        # Extract values from the modal
        persona_name = self._name_input.value
        content = self._content_input.value
        is_public = self._is_public_input.values[0].lower() == "public"
        
        allowed_role_ids = _parse_allowed_set(self._allowed_role_ids.value)

        # Call the provided callback with the collected data
        await self.callback(interaction, persona_name, content, is_public, allowed_role_ids)

    async def on_error(self, interaction: Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing the modal.", ephemeral=True)

class CreatePersonaModal(BasePersonaModal):
    def __init__(self, callback):
        super().__init__(title="Create Persona", callback=callback)

class EditPersonaModal_Owner(BasePersonaModal):
    def __init__(self, persona_id: int, persona_name: str, content: str, is_public: bool, allowed_role_ids: set[int], callback):
        super().__init__(title="Edit Persona", callback=callback, persona_name=persona_name, content=content, is_public=is_public, allowed_role_ids=allowed_role_ids)
        self.persona_id = persona_id

    async def on_submit(self, interaction: Interaction):
        # Extract values from the modal
        persona_name = self._name_input.value
        content = self._content_input.value
        is_public = self._is_public_input.values[0].lower() == "public"
        allowed_role_ids = _parse_allowed_set(self._allowed_role_ids.value)

        # Call the provided callback with the updated data
        await self.callback(interaction, self.persona_id, persona_name, content, is_public, allowed_role_ids)

class EditPersonaModal_TeamMember(BasePersonaModal):
    # cannot edit is_public and allowed_role_ids
    def __init__(self, persona_id: int, persona_name: str, content: str, callback):
        super().__init__(title="Edit Persona", callback=callback, persona_name=persona_name, content=content)
        self.persona_id = persona_id
    
    async def on_submit(self, interaction: Interaction):
        # Extract values from the modal
        persona_name = self._name_input.value
        content = self._content_input.value

        # Call the provided callback with the updated data
        await self.callback(interaction, self.persona_id, persona_name, content)