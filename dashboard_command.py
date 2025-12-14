# dashboard_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

LEDGER_FILE = "ledger.json"

# Fonction pour charger le grand livre des dépenses
def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w") as f:
            json.dump({}, f)
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)

# Emojis/Icons pour un affichage plus joli
ICONS = {
    "Tournée": "🍺",
    "Viennoiserie": "🥐",
    "Kebab": "🌯",
    "Café": "☕"
}

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ======================================================================
    # 1. /dashboard (Vue Détaillée)
    # ======================================================================
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

LEDGER_FILE = "ledger.json"

# Fonction pour charger le grand livre des dépenses
def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w") as f:
            json.dump({}, f)
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)

# Emojis/Icons pour un affichage plus joli
ICONS = {
    "Tournée": "🍺",
    "Viennoiserie": "🥐",
    "Kebab": "🌯",
    "Café": "☕"
}

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ======================================================================
    # 1. /dashboard (Vue Détaillée - Compacte)
    # ======================================================================
    @app_commands.command(name="dashboard", description="Show the full tab dashboard with details.")
    async def dashboard(self, interaction: discord.Interaction):

        ledger = load_ledger()

        if not ledger:
            return await interaction.response.send_message(
                "📭 The tab is empty.", ephemeral=True
            )

        embed = discord.Embed(
            title="🧾 Grand Livre Détaillé",
            description="Liste complète de toutes les entrées enregistrées.",
            color=discord.Color.blue() # Changement de couleur pour varier
        )
        
        # Compteur pour savoir si on a ajouté quelque chose
        entry_count = 0 

        for user_id, entries in ledger.items():
            user = interaction.guild.get_member(int(user_id))
            username = user.display_name if user else f"ID: {user_id}"

            # Ajout d'un titre de section pour l'utilisateur
            embed.add_field(name=f"\u200b", value=f"\u200b", inline=False) # Ligne vide pour la séparation
            embed.add_field(
                name=f"--- 👤 {username} ---", 
                value="**\u200b**", 
                inline=False
            )
            
            # Affichage des entrées de l'utilisateur en ligne
            for i, entry in enumerate(entries):
                emoji = ICONS.get(entry["item"], "❓")
                reason = entry.get("reason")
                added_by_id = entry["added_by"]
                added_by = interaction.guild.get_member(added_by_id)
                added_by_name = added_by.display_name if added_by else f"ID: {added_by_id}"
                
                # Le nom du champ affiche l'Item et la quantité
                field_name = f"{emoji} {entry['item']} × {entry['amount']}"
                
                # La valeur du champ affiche les détails (Raison + Ajouté par)
                field_value = (
                    f"**Raison :** {'*' + reason + '*' if reason else 'Aucune'}\n"
                    f"**Ajouté par :** {added_by.mention if added_by else added_by_name}"
                )
                
                # On utilise inline=True pour avoir 2 ou 3 colonnes si l'écran le permet
                embed.add_field(name=field_name, value=field_value, inline=True)
                entry_count += 1
        
        # Ajout d'un footer pour la date et le compte
        embed.set_footer(text=f"Total: {entry_count} entrées | Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        await interaction.response.send_message(embed=embed)


    # ======================================================================
    # 2. /dashboardsummary (Vue Résumée - Inchangé)
    # ======================================================================
    @app_commands.command(name="dashboardsummary", description="Show tab summary.")
    async def dashboardsummary(self, interaction: discord.Interaction):

        ledger = load_ledger()

        if not ledger:
            return await interaction.response.send_message(
                "📭 No entries in the tab.", ephemeral=True
            )

        embed = discord.Embed(
            title="📈 Récapitulatif du Tab",
            description="Totaux consolidés par utilisateur et par item.",
            color=discord.Color.green()
        )

        summary = {}

        # 1. Aggregate items
        for user_id, entries in ledger.items():
            if user_id not in summary:
                summary[user_id] = {}

            for entry in entries:
                item = entry["item"]
                amount = entry["amount"]
                summary[user_id][item] = summary[user_id].get(item, 0) + amount

        # 2. Display summary fields
        for user_id, items in summary.items():
            user = interaction.guild.get_member(int(user_id))
            username = user.display_name if user else f"ID: {user_id}"

            # Construire la liste des totaux
            lines = [
                f"{ICONS.get(item, '❓')} **{item}** : **{amount}**"
                for item, amount in items.items()
            ]

            embed.add_field(
                name=f"👤 {username}",
                value="\n".join(lines),
                inline=True 
            )
        
        embed.set_footer(text=f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")


        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))

    # ======================================================================
    # 2. /dashboardsummary (Vue Résumée)
    # ======================================================================
    @app_commands.command(name="dashboardsummary", description="Show tab summary.")
    async def dashboardsummary(self, interaction: discord.Interaction):

        ledger = load_ledger()

        if not ledger:
            return await interaction.response.send_message(
                "📭 No entries in the tab.", ephemeral=True
            )

        embed = discord.Embed(
            title="📈 Récapitulatif du Tab",
            description="Totaux consolidés par utilisateur et par item.",
            color=discord.Color.green()
        )

        summary = {}

        # 1. Aggregate items
        for user_id, entries in ledger.items():
            if user_id not in summary:
                summary[user_id] = {}

            for entry in entries:
                item = entry["item"]
                amount = entry["amount"]
                summary[user_id][item] = summary[user_id].get(item, 0) + amount

        # 2. Display summary fields
        for user_id, items in summary.items():
            user = interaction.guild.get_member(int(user_id))
            username = user.display_name if user else f"ID: {user_id}"

            # Construire la liste des totaux avec un format plus propre
            lines = [
                f"{ICONS.get(item, '❓')} **{item}** : **{amount}**"
                for item, amount in items.items()
            ]

            embed.add_field(
                name=f"👤 {username}",
                value="\n".join(lines),
                inline=True # On utilise inline=True ici pour grouper les utilisateurs
            )
        
        embed.set_footer(text=f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")


        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))