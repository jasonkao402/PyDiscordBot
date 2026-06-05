from discord.ui import Modal, TextInput, Select, Label
from discord import Interaction, Message, TextStyle, SelectOption, Member, User
from typing import Optional

from persona_db.DatabaseModels import Persona
from persona_db.helper_func import _join_uid_list, _split_uid_list

class BasePersonaModal(Modal):
    def __init__(self, title: str, callback, is_owner: bool, _persona: Optional[Persona] = None):
        super().__init__(title=title)
        self.callback = callback
        self.is_owner = is_owner
        self.persona_uid = _persona.uid if _persona else -1
        self._default_values = {
            "persona_name": _persona.persona_name if _persona else "",
            "content": _persona.content if _persona else "",
            "is_public": _persona.is_public if _persona else False,
            "allowed_role_ids_str": _join_uid_list(_persona.allowed_role_ids) if _persona else "",
            "allowed_role_ids_set": set(_persona.allowed_role_ids) if _persona else set(),
        }
        
        # Add fields to the modal
        self._name = Label(
            text="Persona Name",
            component=TextInput(
                default=self._default_values["persona_name"],
                placeholder="Enter persona name",
                required=True,
            )
        )
        self._content = Label(
            text="Content",
            component=TextInput(
                default=self._default_values["content"],
                placeholder="Enter persona content",
                style=TextStyle.paragraph,
                required=True,
            )
        )
        _options = [
            SelectOption(label="Public", value="1", default=self._default_values["is_public"]),
            SelectOption(label="Private", value="0", default=not self._default_values["is_public"]),
        ]
        # allowed_role_ids_str = ",".join(str(role_id) for role_id in allowed_role_ids)
        self._is_public = Label(
            text="Select visibility", 
            component=
            Select(
                placeholder="Select visibility", options=_options, min_values=1, max_values=1
            ))
        self._allowed_role_ids = Label(
            text="Allowed Roles",
            component=TextInput(
                default=self._default_values["allowed_role_ids_str"],
                placeholder="Enter role IDs (comma-separated)",
                required=False,
            )
        )
        self.add_item(self._name)
        self.add_item(self._content)
        if is_owner:
            self.add_item(self._is_public)
            self.add_item(self._allowed_role_ids)

    async def on_submit(self, interaction: Interaction):
        # Ensure the components are of the expected types
        assert isinstance(self._name.component, TextInput)
        assert isinstance(self._content.component, TextInput)
        assert isinstance(self._is_public.component, Select)
        assert isinstance(self._allowed_role_ids.component, TextInput)
        
        # Extract values from the modal
        persona_name = self._name.component.value
        content = self._content.component.value
        is_public = self._is_public.component.values[0] == "1" if self.is_owner else self._default_values["is_public"]
        allowed_role_ids = self._allowed_role_ids.component.value if self.is_owner else self._default_values["allowed_role_ids_str"]
        
        # Call the provided callback with the collected data
        await self.callback(interaction, self.persona_uid, persona_name, content, is_public, allowed_role_ids)

    async def on_error(self, interaction: Interaction, error: Exception):
        await interaction.response.send_message(
            f"An error occurred while processing the modal.\n{error}"
        )
        
class CreatePersonaModal(BasePersonaModal):
    def __init__(self, callback):
        super().__init__(title="Create Persona", callback=callback, is_owner=True)
        
class EditPersonaModal_Full(BasePersonaModal):
    def __init__(
        self,
        _persona: Persona,
        callback,
    ):
        super().__init__(
            title="Edit Persona",
            callback=callback,
            is_owner=True,
            _persona=_persona
        )

class EditPersonaModal_Basic(BasePersonaModal):
    # cannot edit is_public and allowed_role_ids
    def __init__(
        self, 
        _persona: Persona, 
        callback
    ):
        super().__init__(
            title="Edit Persona",
            callback=callback,
            is_owner=False,
            _persona=_persona
        )

class TestSelect(Modal, title="Test Select Modal"):
    _options = [
        SelectOption(label="Option 1", value="option_1"),
        SelectOption(label="Option 2", value="option_2"),
        SelectOption(label="Option 3", value="option_3"),
    ]
    label = Label(
        text="Please select an option:",
        component=Select(
            placeholder="Choose an option...",
            required=True,
            options = _options,
            min_values=1,
            max_values=1,
        ),
    )
    reason = Label(
        text="for debugging, just input anything here",
        component=TextInput(
            placeholder="for debugging, just input anything here",
            required=True,
        )
    )
    def __init__(self, member: Member | User):
        super().__init__()
        self.member = member
    
    async def on_submit(self, interaction: Interaction):
        assert isinstance(self.label.component, Select)
        _value = self.label.component.values[0]
        # print(f"{self.member.display_name} selected: {selected_value}")
        # assert isinstance(self.reason.component, TextInput)
        # _value = self.reason.component.value
        # print(f"{self.member.display_name} reason: {_value}")
        await interaction.response.send_message(f"You selected: {_value}")

    async def on_error(self, interaction: Interaction, error: Exception):
        print(f"Error in TestSelect modal: {error}")
        await interaction.response.send_message(f"An error occurred: {error}")