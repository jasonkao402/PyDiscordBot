from discord.ui import Modal, TextInput
from discord import Color, Interaction, Message,TextStyle

class BasePersonaModal(Modal):
    def __init__(self, title: str, callback, persona_name: str = "", content: str = "", visibility: bool = True):
        super().__init__(title=title)
        self.callback = callback

        # Add fields to the modal
        self.add_item(TextInput(label="Persona Name", default=persona_name, placeholder="Enter persona name", required=True))
        self.add_item(TextInput(label="Content", default=content, placeholder="Enter persona content", style=TextStyle.paragraph, required=True))
        self.add_item(TextInput(label="Visibility (public/private)", default="public" if visibility else "private", placeholder="public or private", required=True))

    async def on_submit(self, interaction: Interaction):
        # Extract values from the modal
        persona_name = self.children[0].value
        content = self.children[1].value
        visibility = self.children[2].value.lower() == "public"

        # Call the provided callback with the collected data
        await self.callback(interaction, persona_name, content, visibility)

    async def on_error(self, interaction: Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing the modal.", ephemeral=True)

class CreatePersonaModal(BasePersonaModal):
    def __init__(self, callback):
        super().__init__(title="Create Persona", callback=callback)

class EditPersonaModal(BasePersonaModal):
    def __init__(self, persona_id: int, persona_name: str, content: str, visibility: bool, callback):
        super().__init__(title="Edit Persona", callback=callback, persona_name=persona_name, content=content, visibility=visibility)
        self.persona_id = persona_id

    async def on_submit(self, interaction: Interaction):
        # Extract values from the modal
        persona_name = self.children[0].value
        content = self.children[1].value
        visibility = self.children[2].value.lower() == "public"

        # Call the provided callback with the updated data
        await self.callback(interaction, self.persona_id, persona_name, content, visibility)
