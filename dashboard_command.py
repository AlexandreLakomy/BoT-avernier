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


# ============================================================
# 🔵 PAGINATION VIEW (boutons)
# ============================================================
class DashboardView(discord.ui.View):
    def __init__(self, pages, user):
        super().__init__(timeout=90)  # expire après 90 sec d'inactivité
        self.pages = pages
        self.page = 0
        self.user = user  # seule cette personne peut cliquer

    async def update_message(self, interaction):
        embed = self.pages[self.page]
        await interaction.response.edit_message(embed=embed, view=self)

    # Bouton précédent
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def previous(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux pas utiliser ces boutons.", ephemeral=True
            )

        if self.page > 0:
            self.page -= 1

        await self.update_message(interaction)

    # Bouton suivant
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux pas utiliser ces boutons.", ephemeral=True
            )

        if self.page < len(self.pages) - 1:
            self.page += 1

        await self.update_message(interaction)

    # Bouton fermer
    @discord.ui.button(label="🗑️ Fermer", style=discord.ButtonStyle.danger)
    async def close(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux pas utiliser ces boutons.", ephemeral=True
            )

        await interaction.response.edit_message(content="Dashboard fermé.", embed=None, view=None)



# ============================================================
# 🔵 COG DASHBOARD
# ============================================================
class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========================================================
    # /dashboard → complet ou par utilisateur
    # ========================================================
    @app_commands.command(name="dashboard", description="Affiche le dashboard complet ou celui d'un utilisateur.")
    @app_commands.describe(user="Utilisateur dont vous souhaitez afficher les détails (optionnel)")
    async def dashboard(self, interaction: discord.Interaction, user: discord.User | None = None):

        ledger = load_ledger()

        if not ledger:
            return await interaction.response.send_message("📭 The tab is empty.", ephemeral=True)

        await interaction.response.defer()

        # =====================================================
        # 1️⃣ MODE INDIVIDUEL → PAS DE PAGINATION
        # =====================================================
        if user:
            user_id = str(user.id)

            if user_id not in ledger:
                return await interaction.followup.send(
                    f"❌ Aucun enregistrement trouvé pour {user.mention}.",
                    ephemeral=True
                )

            entries = ledger[user_id]

            embed = discord.Embed(
                title=f"⸻ ✦ {user.display_name} ✦ ⸻",
                description="",
                color=discord.Color.blue()
            )

            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)

            for entry in entries:
                emoji = ICONS.get(entry["item"], "❓")
                reason = entry.get("reason")
                added_by = interaction.guild.get_member(entry["added_by"])

                embed.add_field(
                    name=f"{emoji} {entry['item']} × {entry['amount']}",
                    value=(
                        f"**Raison :** {'*' + reason + '*' if reason else 'Aucune'}\n"
                        f"**Ajouté par :** {added_by.display_name if added_by else 'Inconnu'}\n⠀"
                    ),
                    inline=True
                )

            embed.set_footer(text=f"Mis à jour le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            return await interaction.followup.send(embed=embed)

        # =====================================================
        # 2️⃣ MODE COMPLET → PAGINATION
        # =====================================================
        pages = []           # liste d'embeds générés
        current_embed = None
        char_count = 0       # compte le nombre de caractères dans cette page

        def new_page():
            return discord.Embed(
                title="🧾 Grand Livre Détaillé",
                description="Liste complète de toutes les entrées enregistrées.",
                color=discord.Color.blue()
            )

        current_embed = new_page()

        TOTAL_LIMIT = 5500  # limite prudente par page
        entry_count = 0

        for user_id, entries in ledger.items():
            member = interaction.guild.get_member(int(user_id))

            header_text = f"**⸻ ✦ {member.mention} ✦ ⸻**\n"
            header_len = len(header_text)

            # créer une nouvelle page si nécessaire
            if char_count + header_len > TOTAL_LIMIT:
                pages.append(current_embed)
                current_embed = new_page()
                char_count = 0

            current_embed.add_field(name="⠀", value=header_text, inline=False)
            char_count += header_len

            for entry in entries:
                emoji = ICONS.get(entry["item"], "❓")
                reason = entry.get("reason")
                added_by = interaction.guild.get_member(entry["added_by"])

                value = (
                    f"**Raison :** {'*' + reason + '*' if reason else 'Aucune'}\n"
                    f"**Ajouté par :** {added_by.display_name if added_by else 'Inconnu'}\n⠀"
                )

                entry_text_length = len(value) + len(entry["item"])

                # Nouvelle page ?
                if char_count + entry_text_length > TOTAL_LIMIT:
                    pages.append(current_embed)
                    current_embed = new_page()
                    char_count = 0

                current_embed.add_field(
                    name=f"{emoji} {entry['item']} × {entry['amount']}",
                    value=value,
                    inline=True
                )

                char_count += entry_text_length
                entry_count += 1

        # dernière page
        pages.append(current_embed)

        # Pagination
        view = DashboardView(pages, interaction.user)

        # renvoi de la page 0
        await interaction.followup.send(embed=pages[0], view=view)


    @app_commands.command(name="dashboardsummary", description="Affiche un résumé consolidé des consommations")
    async def dashboardsummary(self, interaction: discord.Interaction):

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

        for user_id, entries in ledger.items():
            if user_id not in summary:
                summary[user_id] = {}

            for entry in entries:
                item = entry["item"]
                summary[user_id][item] = summary[user_id].get(item, 0) + entry["amount"]
                grand_total[item] = grand_total.get(item, 0) + entry["amount"]

        for user_id, items in summary.items():
            member = interaction.guild.get_member(int(user_id))
            username = member.mention if member else f"`Utilisateur inconnu ({user_id})`"

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

        total_lines = [f"{ICONS.get(i, '❓')} {a}" for i, a in sorted(grand_total.items())]

        embed.add_field(name="⠀", value="**━━━━━━━━━━━━━━**", inline=False)
        embed.add_field(name="📈 Total Général", value=" • ".join(total_lines), inline=False)

        embed.set_footer(text=f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
