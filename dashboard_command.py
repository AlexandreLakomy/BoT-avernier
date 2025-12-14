# dashboard_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

LEDGER_FILE = "ledger.json"

def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w") as f:
            json.dump({}, f)
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)

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

            embed.add_field(
                name="⠀",  # caractère invisible pour que Discord accepte le champ
                value=f"**⸻ ✦ {user.mention} ✦ ⸻**",
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
                    f"**Ajouté par :** {added_by.display_name if added_by else added_by_name}\n"
                    f"⠀"
                )
                
                # On utilise inline=True pour avoir 2 ou 3 colonnes si l'écran le permet
                embed.add_field(name=field_name, value=field_value, inline=True)
                entry_count += 1
        
        # Ajout d'un footer pour la date et le compte
        embed.set_footer(text=f"Total: {entry_count} entrées | Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dashboardsummary", description="Affiche un résumé consolidé des consommations")
    async def dashboardsummary(self, interaction: discord.Interaction):

        # IMPORTANT : empêche Discord d'annuler la commande
        await interaction.response.defer()

        ledger = load_ledger()

        if not ledger:
            embed = discord.Embed(
                title="📭 Aucune donnée",
                description="Personne n'a encore rien consommé.",
                color=discord.Color.greyple()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="📊 Résumé Global",
            description="Synthèse des consommations par utilisateur.",
            color=discord.Color.green()
        )

        summary = {}
        grand_total = {}

        # Agrégation des totaux
        for user_id, entries in ledger.items():
            if user_id not in summary:
                summary[user_id] = {}

            for entry in entries:
                item = entry["item"]
                amount = entry["amount"]

                summary[user_id][item] = summary[user_id].get(item, 0) + amount
                grand_total[item] = grand_total.get(item, 0) + amount

        # Section par utilisateur
        for user_id, items in summary.items():
            user = interaction.guild.get_member(int(user_id))
            username = user.mention if user else f"`Utilisateur inconnu ({user_id})`"

            embed.add_field(
                name="⠀",
                value=f"**⸻ ✦ {username} ✦ ⸻**",
                inline=False
            )

            lines = []
            for item, amount in sorted(items.items()):
                emoji = ICONS.get(item, "❓")
                lines.append(f"{emoji} **{item}** : `×{amount}`")

            embed.add_field(
                name="Consommations",
                value="\n".join(lines),
                inline=True
            )

        # TOTAL GLOBAL
        if grand_total:
            total_lines = []
            for item, amount in sorted(grand_total.items()):
                emoji = ICONS.get(item, "❓")
                total_lines.append(f"{emoji} {amount}")

            embed.add_field(
                name="⠀",
                value="**━━━━━━━━━━━━━━**",
                inline=False
            )

            embed.add_field(
                name="📈 Total Général",
                value=" • ".join(total_lines),
                inline=False
            )

        embed.set_footer(text=f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))