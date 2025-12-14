# add_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

LEDGER_FILE = "ledger.json"
PENDING_FILE = "pending.json"
REQUIRED_VOTES = 1  # Modulable ici

def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w") as f:
            json.dump({}, f)
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)

def save_ledger(data):
    with open(LEDGER_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_pending():
    if not os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "w") as f:
            json.dump({}, f)
    with open(PENDING_FILE, "r") as f:
        return json.load(f)

def save_pending(data):
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f, indent=4)

ICONS = {
    "Tournée": "🍺",
    "Viennoiserie": "🥐",
    "Kebab": "🌯",
    "Café": "☕"
}

class ReasonModal(discord.ui.Modal, title="Ajouter une raison"):
    reason = discord.ui.TextInput(
        label="Raison (optionnelle)",
        placeholder="Pourquoi cette tournée ? (max 100 caractères)",
        max_length=100,
        required=False
    )

    def __init__(self, user, item, amount):
        super().__init__()
        self.target_user = user
        self.item = item
        self.amount = amount

    async def on_submit(self, interaction: discord.Interaction):
        pending = load_pending()
        
        # Créer une clé unique pour cette proposition
        proposal_id = f"{interaction.id}"
        
        entry = {
            "user_id": self.target_user.id,
            "item": self.item,
            "amount": self.amount,
            "reason": self.reason.value if self.reason.value else None,
            "added_by": interaction.user.id,
            "timestamp": datetime.now().isoformat(),
            "votes": [],
            "message_id": None
        }
        
        pending[proposal_id] = entry
        save_pending(pending)
        
        # Créer l'embed de proposition
        emoji = ICONS.get(self.item, "❓")
        embed = discord.Embed(
            title="⏳ Proposition de Tournée",
            description=f"Cette proposition nécessite **{REQUIRED_VOTES} 👍** pour être validée",
            color=discord.Color.orange()
        )
        embed.add_field(name="👤 Victime", value=self.target_user.mention, inline=True)
        embed.add_field(name=f"{emoji} Item", value=f"**{self.item}** ×{self.amount}", inline=True)
        embed.add_field(name="📝 Proposé par", value=interaction.user.mention, inline=True)
        
        if self.reason.value:
            embed.add_field(name="💬 Raison", value=f"*{self.reason.value}*", inline=False)
        
        embed.add_field(
            name="━━━━━━━━━━━━━",
            value=f"**0/{REQUIRED_VOTES}** votes • Réagissez avec 👍",
            inline=False
        )
        embed.set_footer(text=f"ID: {proposal_id}")
        
        # Envoyer le message et ajouter la réaction
        msg = await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("👍")
        
        # Sauvegarder l'ID du message
        pending[proposal_id]["message_id"] = message.id
        save_pending(pending)

class AddView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.target_user = user
        self.selected_item = None
        self.selected_amount = None

    @discord.ui.select(
        placeholder="Choisir un item",
        options=[
            discord.SelectOption(label="Tournée", description="Une tournée de boissons", emoji="🍺", value="Tournée"),
            discord.SelectOption(label="Viennoiserie", description="Des croissants, pains au chocolat...", emoji="🥐", value="Viennoiserie"),
            discord.SelectOption(label="Kebab", description="Un bon kebab", emoji="🌯", value="Kebab"),
            discord.SelectOption(label="Café", description="Un café", emoji="☕", value="Café")
        ]
    )
    async def item_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_item = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        placeholder="Choisir la quantité",
        options=[discord.SelectOption(label=f"×{i}", value=str(i)) for i in range(1, 11)]
    )
    async def amount_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_amount = int(select.values[0])
        await interaction.response.defer()

    @discord.ui.button(label="Proposer", style=discord.ButtonStyle.green, emoji="✅")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_item or not self.selected_amount:
            return await interaction.response.send_message(
                "⚠️ Sélectionne **l'item et la quantité** avant de continuer !",
                ephemeral=True
            )
        
        await interaction.response.send_modal(
            ReasonModal(self.target_user, self.selected_item, self.selected_amount)
        )

class AddCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add", description="Proposer une tournée pour quelqu'un")
    @app_commands.describe(user="La personne qui doit la tournée")
    async def add(self, interaction: discord.Interaction, user: discord.User):
        view = AddView(user)
        
        embed = discord.Embed(
            title="➕ Nouvelle Proposition",
            description=f"Proposer une tournée pour **{user.mention}**\n\nChoisis l'item et la quantité :",
            color=discord.Color.blurple()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        
        if str(payload.emoji) != "👍":
            return
        
        pending = load_pending()
        
        # Trouver la proposition correspondant au message
        proposal_id = None
        for pid, data in pending.items():
            if data.get("message_id") == payload.message_id:
                proposal_id = pid
                break
        
        if not proposal_id:
            return
        
        entry = pending[proposal_id]
        
        # Vérifier que l'utilisateur n'a pas déjà voté
        if payload.user_id in entry["votes"]:
            return
        
        # Ajouter le vote
        entry["votes"].append(payload.user_id)
        save_pending(pending)
        
        # Mettre à jour le message
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        votes_count = len(entry["votes"])
        emoji = ICONS.get(entry["item"], "❓")
        
        if votes_count >= REQUIRED_VOTES:
            # Valider la tournée
            ledger = load_ledger()
            uid = str(entry["user_id"])
            
            if uid not in ledger:
                ledger[uid] = []
            
            ledger[uid].append({
                "item": entry["item"],
                "amount": entry["amount"],
                "reason": entry["reason"],
                "added_by": entry["added_by"]
            })
            save_ledger(ledger)
            
            # Supprimer de pending
            del pending[proposal_id]
            save_pending(pending)
            
            # Mettre à jour l'embed
            embed = discord.Embed(
                title="✅ Tournée Validée !",
                description="Cette tournée a été ajoutée au grand livre",
                color=discord.Color.green()
            )
            user = await self.bot.fetch_user(entry["user_id"])
            added_by = await self.bot.fetch_user(entry["added_by"])
            
            embed.add_field(name="👤 Victime", value=user.mention, inline=True)
            embed.add_field(name=f"{emoji} Item", value=f"**{entry['item']}** ×{entry['amount']}", inline=True)
            embed.add_field(name="📝 Proposé par", value=added_by.mention, inline=True)
            
            if entry["reason"]:
                embed.add_field(name="💬 Raison", value=f"*{entry['reason']}*", inline=False)
            
            embed.set_footer(text=f"Validé avec {votes_count} votes")
            
            await message.edit(embed=embed)
            await message.clear_reactions()
        else:
            # Mettre à jour le compte de votes
            embed = message.embeds[0]
            embed.set_field_at(
                -1,
                name="━━━━━━━━━━━━━",
                value=f"**{votes_count}/{REQUIRED_VOTES}** votes • Réagissez avec 👍",
                inline=False
            )
            await message.edit(embed=embed)

    @app_commands.command(name="dashboardpending", description="Affiche les propositions en attente de validation")
    async def dashboardpending(self, interaction: discord.Interaction):
        pending = load_pending()
        
        if not pending:
            embed = discord.Embed(
                title="📭 Aucune proposition",
                description="Il n'y a pas de tournée en attente de validation",
                color=discord.Color.greyple()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = discord.Embed(
            title="⏳ Propositions en Attente",
            description=f"*Nécessitent {REQUIRED_VOTES} votes pour être validées*",
            color=discord.Color.orange()
        )
        
        for proposal_id, entry in pending.items():
            user = await self.bot.fetch_user(entry["user_id"])
            added_by = await self.bot.fetch_user(entry["added_by"])
            emoji = ICONS.get(entry["item"], "❓")
            votes_count = len(entry["votes"])
            
            field_name = f"{emoji} {entry['item']} ×{entry['amount']} pour {user.display_name}"
            field_value = f"**Votes :** {votes_count}/{REQUIRED_VOTES}\n**Par :** {added_by.mention}"
            
            if entry["reason"]:
                field_value += f"\n**Raison :** *{entry['reason']}*"
            
            embed.add_field(name=field_name, value=field_value, inline=False)
        
        embed.set_footer(text=f"{len(pending)} proposition(s) en attente")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AddCommand(bot))