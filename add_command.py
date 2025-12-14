# add_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os

LEDGER_FILE = "ledger.json"

# ========= JSON HANDLING ==========
def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w") as f:
            json.dump({}, f)
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)

def save_ledger(data):
    with open(LEDGER_FILE, "w") as f:
        json.dump(data, f, indent=4)



# ========= MODAL FOR REASON ==========
class ReasonModal(discord.ui.Modal, title="Add a Reason"):
    reason = discord.ui.TextInput(
        label="Reason (optional)",
        placeholder="Why? (max 100 chars)",
        max_length=100,
        required=False
    )

    def __init__(self, user, item, amount):
        super().__init__()
        self.target_user = user
        self.item = item
        self.amount = amount

    async def on_submit(self, interaction: discord.Interaction):
        ledger = load_ledger()

        uid = str(self.target_user.id)
        if uid not in ledger:
            ledger[uid] = []

        entry = {
            "item": self.item,
            "amount": self.amount,
            "reason": self.reason.value,
            "added_by": interaction.user.id
        }

        ledger[uid].append(entry)
        save_ledger(ledger)

        embed = discord.Embed(
            title="📌 Tab Updated",
            color=discord.Color.gold()
        )
        embed.add_field(name="User", value=self.target_user.mention, inline=False)
        embed.add_field(name="Item", value=self.item, inline=True)
        embed.add_field(name="Amount", value=str(self.amount), inline=True)

        if self.reason.value:
            embed.add_field(name="Reason", value=self.reason.value, inline=False)

        embed.set_footer(text=f"Added by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)



# ========= INTERACTIVE VIEW (Dropdown + Button) ==========
class AddView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.target_user = user
        self.selected_item = None
        self.selected_amount = None

    # ITEM DROPDOWN
    @discord.ui.select(
        placeholder="Choose an item",
        options=[
            discord.SelectOption(label="Tournée 🍺", value="Tournée"),
            discord.SelectOption(label="Viennoiserie 🥐", value="Viennoiserie"),
            discord.SelectOption(label="Kebab 🌯", value="Kebab"),
            discord.SelectOption(label="Café ☕", value="Café")
        ]
    )
    async def item_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_item = select.values[0]
        await interaction.response.defer()

    # AMOUNT DROPDOWN
    @discord.ui.select(
        placeholder="Choose amount",
        options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 4)]
    )
    async def amount_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_amount = int(select.values[0])
        await interaction.response.defer()

    # BUTTON TO CONFIRM
    @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.selected_item or not self.selected_amount:
            return await interaction.response.send_message(
                "Please select **both item and amount** before continuing.",
                ephemeral=True
            )

        # Open modal
        await interaction.response.send_modal(
            ReasonModal(self.target_user, self.selected_item, self.selected_amount)
        )



# ========= MAIN COG (Slash Command) ==========
class AddCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add", description="Add a tab entry for a user.")
    @app_commands.describe(user="Target user")
    async def add(self, interaction: discord.Interaction, user: discord.User):

        view = AddView(user)

        await interaction.response.send_message(
            f"Adding an entry for **{user.mention}**.\nChoose item and amount:",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AddCommand(bot))
