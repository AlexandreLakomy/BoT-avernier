# fulfill_command.py

import discord
from discord import app_commands
from discord.ext import commands

import json
import os
from datetime import datetime

# ============================================================
# Constants
# ============================================================

LEDGER_FILE = "ledger.json"
FULFILL_FILE = "fulfillments.json"

ICONS = {
    "Tournée": "🍺",
    "Viennoiserie": "🥐",
    "Kebab": "🌯",
    "Café": "☕",
}

# ============================================================
# JSON Helpers
# ============================================================

def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return {}
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)


def save_ledger(data):
    with open(LEDGER_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_fulfillments():
    if not os.path.exists(FULFILL_FILE):
        return []
    with open(FULFILL_FILE, "r") as f:
        return json.load(f)


def save_fulfillments(data):
    with open(FULFILL_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ============================================================
# MODAL : Commentaire
# ============================================================

class FulfillModal(discord.ui.Modal, title="Ajouter un commentaire"):

    comment = discord.ui.TextInput(
        label="Commentaire (optionnel)",
        placeholder="Ex : payé au bar",
        max_length=100,
        required=False,
    )

    def __init__(self, user_id, item, amount):
        super().__init__()
        self.user_id = user_id
        self.item = item
        self.amount = amount

    async def on_submit(self, interaction: discord.Interaction):
        ledger = load_ledger()
        fulfillments = load_fulfillments()

        uid = str(self.user_id)
        remaining = self.amount

        # Décrémentation des dettes existantes
        for entry in ledger.get(uid, []):
            if entry["item"] != self.item:
                continue

            if remaining <= 0:
                break

            if entry["amount"] <= remaining:
                remaining -= entry["amount"]
                entry["amount"] = 0
            else:
                entry["amount"] -= remaining
                remaining = 0

        # Suppression des entrées soldées
        ledger[uid] = [e for e in ledger.get(uid, []) if e["amount"] > 0]
        save_ledger(ledger)

        # Historique
        fulfillments.append({
            "user_id": self.user_id,
            "item": self.item,
            "amount": self.amount,
            "comment": self.comment.value or None,
            "fulfilled_at": datetime.now().isoformat(),
        })
        save_fulfillments(fulfillments)

        await interaction.response.edit_message(
            content=(
                "✅ **Acquittement enregistré**\n"
                f"{ICONS[self.item]} {self.item} ×{self.amount}\n"
                f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
            embed=None,
            view=None,
        )

# ============================================================
# VIEW : Sélection item + quantité
# ============================================================

class FulfillView(discord.ui.View):

    def __init__(self, user, items_due):
        super().__init__(timeout=120)

        self.user = user
        self.item = None
        self.amount = None

        # -------- SELECT ITEM --------
        item_options = [
            discord.SelectOption(
                label=f"{item} (×{total} restant)",
                emoji=ICONS.get(item, "❓"),
                value=item,
            )
            for item, total in items_due.items()
        ]

        self.item_select = discord.ui.Select(
            placeholder="Choisir l'item à acquitter",
            options=item_options,
        )
        self.item_select.callback = self.on_item_select
        self.add_item(self.item_select)

        # -------- SELECT AMOUNT --------
        self.amount_select = discord.ui.Select(
            placeholder="Choisir la quantité",
            options=[
                discord.SelectOption(label=f"×{i}", value=str(i))
                for i in range(1, 6)
            ],
        )
        self.amount_select.callback = self.on_amount_select
        self.add_item(self.amount_select)

    async def on_item_select(self, interaction: discord.Interaction):
        self.item = self.item_select.values[0]
        await interaction.response.defer()

    async def on_amount_select(self, interaction: discord.Interaction):
        self.amount = int(self.amount_select.values[0])
        await interaction.response.defer()

    @discord.ui.button(
        label="Acquitter",
        style=discord.ButtonStyle.green,
        emoji="✅",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.item or not self.amount:
            return await interaction.response.send_message(
                "⚠️ Sélectionne l'item et la quantité.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            FulfillModal(self.user.id, self.item, self.amount)
        )

# ============================================================
# COMMAND
# ============================================================

class FulfillCommand(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="fulfill",
        description="Acquitter une ou plusieurs tournées",
    )
    @app_commands.describe(
        user="La personne qui acquitte la tournée",
    )
    async def fulfill(
        self,
        interaction: discord.Interaction,
        user: discord.User,
    ):
        if interaction.user.id != user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux acquitter que tes propres tournées.",
                ephemeral=True,
            )

        # Obligatoire avant followup
        await interaction.response.defer(ephemeral=True)

        ledger = load_ledger()
        uid = str(user.id)

        if uid not in ledger or not ledger[uid]:
            return await interaction.followup.send(
                "🎉 Tu n'as aucune tournée à acquitter.",
                ephemeral=True,
            )

        items_due = {}
        for entry in ledger[uid]:
            item = entry["item"]
            items_due[item] = items_due.get(item, 0) + entry["amount"]

        embed = discord.Embed(
            title="💸 Acquitter une tournée",
            description="Choisis l'item et la quantité à acquitter",
            color=discord.Color.green(),
        )

        await interaction.followup.send(
            embed=embed,
            view=FulfillView(user, items_due),
            ephemeral=True,
        )

# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(FulfillCommand(bot))
