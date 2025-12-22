# dashboard_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
import traceback

LEDGER_FILE = "ledger.json"
PAGE_CHAR_LIMIT = 5500  # Limite de sécurité par page
MAX_FIELDS_PER_PAGE = 24  # Discord limite à 25 fields, on garde une marge


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
        super().__init__(timeout=90)
        self.pages = pages
        self.page = 0
        self.user = user
        self.update_buttons()

    def update_buttons(self):
        """Active/désactive les boutons selon la page actuelle"""
        self.children[0].disabled = (self.page == 0)  # Bouton précédent
        self.children[1].disabled = (self.page >= len(self.pages) - 1)  # Bouton suivant

    async def update_message(self, interaction):
        self.update_buttons()
        embed = self.pages[self.page]
        # Ajouter le numéro de page dans le footer
        embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)} • Mis à jour le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def previous(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux pas utiliser ces boutons.", ephemeral=True
            )
        if self.page > 0:
            self.page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ Tu ne peux pas utiliser ces boutons.", ephemeral=True
            )
        if self.page < len(self.pages) - 1:
            self.page += 1
        await self.update_message(interaction)

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

    def estimate_user_section_size(self, user_id, entries):
        """Estime la taille d'une section utilisateur complète"""
        try:
            # Header approximatif (mention Discord = ~20 caractères environ)
            header_text = f"**⸻ ✦ <@{user_id}> ✦ ⸻**\n"
            total_size = len(header_text) + 50  # Marge pour le field name
            
            # Chaque entrée
            for entry in entries:
                emoji = ICONS.get(entry["item"], "❓")
                reason = entry.get("reason", "")
                
                # Titre du field
                field_name = f"{emoji} {entry['item']} × {entry['amount']}"
                total_size += len(field_name)
                
                # Valeur du field (estimation large)
                reason_text = reason if reason else "Aucune"
                value_estimate = len(f"**Raison :** {reason_text}\n**Ajouté par :** Utilisateur inconnu\n⠀")
                total_size += value_estimate + 100  # Marge de sécurité
            
            print(f"[DEBUG] User {user_id} estimated size: {total_size}")
            return total_size
        except Exception as e:
            print(f"[ERROR] estimate_user_section_size: {e}")
            traceback.print_exc()
            return 1000  # Valeur par défaut en cas d'erreur

    @app_commands.command(name="dashboard", description="Affiche le dashboard complet ou celui d'un utilisateur.")
    @app_commands.describe(user="Utilisateur dont vous souhaitez afficher les détails (optionnel)")
    async def dashboard(self, interaction: discord.Interaction, user: discord.User | None = None):
        try:
            print(f"[DEBUG] Dashboard command called by {interaction.user}")
            ledger = load_ledger()
            print(f"[DEBUG] Ledger loaded, {len(ledger)} users found")

            if not ledger:
                print("[DEBUG] Ledger is empty")
                return await interaction.response.send_message("📭 The tab is empty.", ephemeral=True)

            print("[DEBUG] Deferring response...")
            await interaction.response.defer()
            print("[DEBUG] Response deferred successfully")

            # =====================================================
            # 1️⃣ MODE INDIVIDUEL → PAS DE PAGINATION
            # =====================================================
            if user:
                print(f"[DEBUG] Individual mode for user {user.id}")
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
            # 2️⃣ MODE COMPLET → PAGINATION INTELLIGENTE
            # =====================================================
            print("[DEBUG] Starting full dashboard mode with pagination")
            pages = []
            current_embed = discord.Embed(
                title="🧾 Grand Livre Détaillé",
                description="Liste complète de toutes les entrées enregistrées.",
                color=discord.Color.blue()
            )
            
            # Taille de base de l'embed (titre + description)
            base_size = len(current_embed.title or "") + len(current_embed.description or "")
            current_page_size = base_size
            print(f"[DEBUG] Base embed size: {base_size}")

            user_count = 0
            for user_id, entries in ledger.items():
                user_count += 1
                print(f"[DEBUG] Processing user {user_count}/{len(ledger)}: {user_id} with {len(entries)} entries")
                
                # Estimer la taille de cette section utilisateur
                user_section_size = self.estimate_user_section_size(user_id, entries)
                # Nombre de fields que cet utilisateur va ajouter (1 header + N entries)
                user_fields_count = 1 + len(entries)
                
                print(f"[DEBUG] Current: {len(current_embed.fields)} fields, {current_page_size} chars")
                print(f"[DEBUG] User will add: {user_fields_count} fields, {user_section_size} chars")
                print(f"[DEBUG] Total would be: {len(current_embed.fields) + user_fields_count} fields, {current_page_size + user_section_size} chars")
                
                # Si ajouter cet utilisateur dépasse une limite, créer une nouvelle page
                will_exceed_fields = (len(current_embed.fields) + user_fields_count > MAX_FIELDS_PER_PAGE)
                will_exceed_chars = (current_page_size + user_section_size > PAGE_CHAR_LIMIT)
                
                if (will_exceed_fields or will_exceed_chars) and len(current_embed.fields) > 0:
                    print(f"[DEBUG] Page full! (fields: {will_exceed_fields}, chars: {will_exceed_chars})")
                    print(f"[DEBUG] Creating new page. Current page has {len(current_embed.fields)} fields")
                    pages.append(current_embed)
                    current_embed = discord.Embed(
                        title="🧾 Grand Livre Détaillé",
                        description="Liste complète de toutes les entrées enregistrées.",
                        color=discord.Color.blue()
                    )
                    current_page_size = base_size
                
                # Récupérer le membre
                print(f"[DEBUG] Fetching member for user_id {user_id}")
                member = interaction.guild.get_member(int(user_id))
                member_mention = member.mention if member else f"<@{user_id}>"
                print(f"[DEBUG] Member mention: {member_mention}")
                
                # Ajouter le header de l'utilisateur
                header_text = f"**⸻ ✦ {member_mention} ✦ ⸻**\n"
                current_embed.add_field(name="⠀", value=header_text, inline=False)
                current_page_size += len(header_text)
                print(f"[DEBUG] Added user header, new page size: {current_page_size}")
                
                # Ajouter toutes les entrées de cet utilisateur
                entry_count = 0
                for entry in entries:
                    entry_count += 1
                    emoji = ICONS.get(entry["item"], "❓")
                    reason = entry.get("reason")
                    added_by = interaction.guild.get_member(entry["added_by"])

                    field_name = f"{emoji} {entry['item']} × {entry['amount']}"
                    field_value = (
                        f"**Raison :** {'*' + reason + '*' if reason else 'Aucune'}\n"
                        f"**Ajouté par :** {added_by.display_name if added_by else 'Inconnu'}\n⠀"
                    )

                    current_embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=True
                    )
                    current_page_size += len(field_name) + len(field_value)
                    print(f"[DEBUG] Added entry {entry_count}/{len(entries)}, page size: {current_page_size}")

            # Ajouter la dernière page
            if len(current_embed.fields) > 0:
                print(f"[DEBUG] Adding final page with {len(current_embed.fields)} fields")
                pages.append(current_embed)

            print(f"[DEBUG] Total pages created: {len(pages)}")

            # Si aucune page n'a été créée (ne devrait pas arriver)
            if not pages:
                print("[ERROR] No pages were created!")
                return await interaction.followup.send("❌ Erreur lors de la génération du dashboard.", ephemeral=True)

            # Si une seule page, pas besoin de pagination
            if len(pages) == 1:
                print("[DEBUG] Single page, sending without pagination")
                pages[0].set_footer(text=f"Mis à jour le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                return await interaction.followup.send(embed=pages[0])

            # Pagination avec boutons
            print(f"[DEBUG] Multiple pages ({len(pages)}), creating pagination view")
            view = DashboardView(pages, interaction.user)
            pages[0].set_footer(text=f"Page 1/{len(pages)} • Mis à jour le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            print("[DEBUG] Sending first page with view...")
            await interaction.followup.send(embed=pages[0], view=view)
            print("[DEBUG] Dashboard sent successfully!")

        except Exception as e:
            print(f"[ERROR] Dashboard command failed: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)
            except:
                print("[ERROR] Could not send error message to user")

    @app_commands.command(name="dashboardsummary", description="Affiche un résumé consolidé des consommations")
    async def dashboardsummary(self, interaction: discord.Interaction):
        try:
            print("[DEBUG] Dashboardsummary command called")
            await interaction.response.defer()
            ledger = load_ledger()

            if not ledger:
                embed = discord.Embed(
                    title="📭 Aucune donnée",
                    description="Personne n'a encore rien consommé.",
                    color=discord.Color.greyple()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)

            # Calculer les résumés
            summary = {}
            grand_total = {}

            for user_id, entries in ledger.items():
                if user_id not in summary:
                    summary[user_id] = {}

                for entry in entries:
                    item = entry["item"]
                    summary[user_id][item] = summary[user_id].get(item, 0) + entry["amount"]
                    grand_total[item] = grand_total.get(item, 0) + entry["amount"]

            print(f"[DEBUG] Summary calculated for {len(summary)} users")

            # Créer les pages avec pagination
            pages = []
            current_embed = discord.Embed(
                title="📊 Résumé Global",
                description="Synthèse des consommations par utilisateur.",
                color=discord.Color.green()
            )
            base_size = len(current_embed.title or "") + len(current_embed.description or "")
            current_page_size = base_size

            for user_id, items in summary.items():
                member = interaction.guild.get_member(int(user_id))
                username = member.mention if member else f"`Utilisateur inconnu ({user_id})`"

                # Calculer la taille de cette section (2 fields: header + consommations)
                # Calculer la taille de cette section
                header_text = f"**   ✦ {username} ✦ ⸻**"
                lines = [
                    f"{ICONS.get(item, '❓')} **{item}** : `×{amount}`"
                    for item, amount in sorted(items.items())
                ]
                consommations_text = "\n".join(lines)

                # section_size = len(header_text) + len(consommations_text)
                section_size = (
                    len(header_text) + len(consommations_text)
                )

                # user_fields_count = 2  # header + consommations
                user_fields_count = 2

                will_exceed_fields = (
                    len(current_embed.fields) + user_fields_count >= MAX_FIELDS_PER_PAGE
                )
                will_exceed_chars = (
                    current_page_size + section_size >= PAGE_CHAR_LIMIT
                )

                if (will_exceed_fields or will_exceed_chars) and len(current_embed.fields) > 0:
                    pages.append(current_embed)
                    current_embed = discord.Embed(
                        title="📊 Résumé Global",
                        description="Synthèse des consommations par utilisateur.",
                        color=discord.Color.green()
                    )
                    current_page_size = base_size

                # Ajouter l'utilisateur
                current_embed.add_field(
                    name="⠀",
                    value=header_text,
                    inline=False
                )
                current_embed.add_field(
                    name="Consommations",
                    value=consommations_text,
                    inline=True
                )
                current_page_size += section_size

            # Ajouter la dernière page
            if len(current_embed.fields) > 0:
                pages.append(current_embed)

            print(f"[DEBUG] Created {len(pages)} summary pages")

            # Ajouter le total général sur la dernière page
            if pages:
                total_lines = [f"{ICONS.get(i, '❓')} {a}" for i, a in sorted(grand_total.items())]
                pages[-1].add_field(name="⠀", value="**━━━━━━━━━━━━━━━━━━━**", inline=False)
                pages[-1].add_field(name="📈 Total Général", value=" • ".join(total_lines), inline=False)

            # Envoyer avec ou sans pagination
            if len(pages) == 1:
                pages[0].set_footer(text=f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                await interaction.followup.send(embed=pages[0])
            else:
                view = DashboardView(pages, interaction.user)
                pages[0].set_footer(text=f"Page 1/{len(pages)} • Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                await interaction.followup.send(embed=pages[0], view=view)

            print("[DEBUG] Dashboardsummary sent successfully")

        except Exception as e:
            print(f"[ERROR] Dashboardsummary failed: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)
            except:
                print("[ERROR] Could not send error message")

async def setup(bot):
    await bot.add_cog(Dashboard(bot))