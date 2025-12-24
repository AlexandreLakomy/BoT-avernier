# add_command.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import traceback
import asyncio
import math

LEDGER_FILE = "ledger.json"
PENDING_FILE = "pending.json"
REQUIRED_VOTES = 1  # Modulable ici
MAX_FIELDS_PER_PAGE = 24  # Limite Discord
PROPOSAL_TIMEOUT = 300  # 5 minutes en secondes pour test (normalement 36000 pour 10h)

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

# ============================================================
# 🔵 PAGINATION VIEW (boutons)
# ============================================================
class PendingView(discord.ui.View):
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
        embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)} • {len(self.pages[0].fields)} proposition(s) en attente")
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


class ReasonModal(discord.ui.Modal, title="Ajouter une raison"):
    reason = discord.ui.TextInput(
        label="Raison (optionnelle)",
        placeholder="Pourquoi cette tournée ? (max 100 caractères)",
        max_length=100,
        required=False
    )

    def __init__(self, user, item, amount, original_view):
        super().__init__()
        self.target_user = user
        self.item = item
        self.amount = amount
        self.original_view = original_view

    async def on_submit(self, interaction: discord.Interaction):
        pending = load_pending()
        
        # Créer une clé unique pour cette proposition
        proposal_id = f"{interaction.id}"
        
        # Calculer l'heure d'expiration
        expires_at = (datetime.now() + timedelta(seconds=PROPOSAL_TIMEOUT)).isoformat()
        
        entry = {
            "user_id": self.target_user.id,
            "item": self.item,
            "amount": self.amount,
            "reason": self.reason.value if self.reason.value else None,
            "added_by": interaction.user.id,
            "timestamp": datetime.now().isoformat(),
            "expires_at": expires_at,
            "votes": [],
            "message_id": None,
            "channel_id": None
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
        
        # Calculer le temps restant initial avec arrondi
        total_minutes = math.ceil(PROPOSAL_TIMEOUT / 60)
        hours_left = total_minutes // 60
        minutes_left = total_minutes % 60
        time_str = f"{hours_left}h{minutes_left}min" if hours_left > 0 else f"{minutes_left}min"
        
        embed.add_field(
            name="━━━━━━━━━━━━━",
            value=f"**0/{REQUIRED_VOTES}** votes • Réagissez avec 👍\n⏰ Expire dans {time_str}",
            inline=False
        )
        embed.set_footer(text=f"ID: {proposal_id}")
        
        # Désactiver le bouton "Proposer" dans le message original
        self.original_view.disable_button()
        
        # Envoyer le message et ajouter la réaction
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("👍")
        
        # Sauvegarder l'ID du message et du canal
        pending[proposal_id]["message_id"] = message.id
        pending[proposal_id]["channel_id"] = message.channel.id
        save_pending(pending)
        
        # Lancer le timer d'expiration et les mises à jour
        bot = interaction.client
        asyncio.create_task(bot.get_cog("AddCommand").check_proposal_expiration(proposal_id))
        asyncio.create_task(bot.get_cog("AddCommand").update_proposal_timer(proposal_id))

class AddView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.target_user = user
        self.selected_item = None
        self.selected_amount = None
        self.button_used = False

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
        if self.button_used:
            return await interaction.response.send_message(
                "⚠️ Vous avez déjà proposé cette tournée !",
                ephemeral=True
            )
        
        if not self.selected_item or not self.selected_amount:
            return await interaction.response.send_message(
                "⚠️ Sélectionne **l'item et la quantité** avant de continuer !",
                ephemeral=True
            )
        
        self.button_used = True
        
        await interaction.response.send_modal(
            ReasonModal(self.target_user, self.selected_item, self.selected_amount, self)
        )
    
    def disable_button(self):
        """Désactive le bouton après utilisation"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

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

    async def check_proposal_expiration(self, proposal_id):
        """Vérifie si une proposition a expiré après le timeout"""
        await asyncio.sleep(PROPOSAL_TIMEOUT)
        
        pending = load_pending()
        
        # Vérifier si la proposition existe encore
        if proposal_id not in pending:
            return
        
        entry = pending[proposal_id]
        votes_count = len(entry["votes"])
        
        # Si le nombre de votes requis n'est pas atteint
        if votes_count < REQUIRED_VOTES:
            # Récupérer le message
            try:
                channel = self.bot.get_channel(entry["channel_id"])
                message = await channel.fetch_message(entry["message_id"])
                
                # Créer l'embed d'annulation
                emoji = ICONS.get(entry["item"], "❓")
                embed = discord.Embed(
                    title="❌ Tournée Annulée",
                    description="Cette proposition n'a pas reçu assez de votes dans le temps imparti",
                    color=discord.Color.red()
                )
                
                user = await self.bot.fetch_user(entry["user_id"])
                added_by = await self.bot.fetch_user(entry["added_by"])
                
                embed.add_field(name="👤 Victime", value=user.mention, inline=True)
                embed.add_field(name=f"{emoji} Item", value=f"**{entry['item']}** ×{entry['amount']}", inline=True)
                embed.add_field(name="📝 Proposé par", value=added_by.mention, inline=True)
                
                if entry["reason"]:
                    embed.add_field(name="💬 Raison", value=f"*{entry['reason']}*", inline=False)
                
                embed.set_footer(text=f"Expiré avec {votes_count}/{REQUIRED_VOTES} votes")
                
                await message.edit(embed=embed)
                await message.clear_reactions()
                
            except Exception as e:
                print(f"[ERROR] Could not update expired proposal: {e}")
            
            # Supprimer de pending
            del pending[proposal_id]
            save_pending(pending)

    async def update_proposal_timer(self, proposal_id):
        """Met à jour le temps restant toutes les minutes"""
        while True:
            await asyncio.sleep(60)  # update toutes les 60s

            pending = load_pending()
            if proposal_id not in pending:
                return  # proposition supprimée / validée

            entry = pending[proposal_id]

            expires_at = datetime.fromisoformat(entry["expires_at"])
            remaining = expires_at - datetime.now()

            if remaining.total_seconds() <= 0:
                return  # expiration gérée ailleurs

            # Arrondir à la minute supérieure
            total_minutes = math.ceil(remaining.total_seconds() / 60)
            hours_left = total_minutes // 60
            minutes_left = total_minutes % 60
            time_str = f"{hours_left}h{minutes_left}min" if hours_left > 0 else f"{minutes_left}min"

            try:
                channel = self.bot.get_channel(entry["channel_id"])
                message = await channel.fetch_message(entry["message_id"])

                embed = message.embeds[0]
                votes_count = len(entry["votes"])

                # Mettre à jour le field avec le timer
                embed.set_field_at(
                    -1,
                    name="━━━━━━━━━━━━━",
                    value=f"**{votes_count}/{REQUIRED_VOTES}** votes • Réagissez avec 👍\n⏰ Expire dans {time_str}",
                    inline=False
                )

                await message.edit(embed=embed)

            except Exception as e:
                print(f"[ERROR] Could not update timer: {e}")
                return  # message supprimé ou erreur → on stop

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
            # Calculer le temps restant avec arrondi à la minute supérieure
            expires_at = datetime.fromisoformat(entry["expires_at"])
            time_left = expires_at - datetime.now()
            total_minutes = math.ceil(time_left.total_seconds() / 60)
            hours_left = total_minutes // 60
            minutes_left = total_minutes % 60
            time_str = f"{hours_left}h{minutes_left}min" if hours_left > 0 else f"{minutes_left}min"
            
            # Mettre à jour le compte de votes
            embed = message.embeds[0]
            embed.set_field_at(
                -1,
                name="━━━━━━━━━━━━━",
                value=f"**{votes_count}/{REQUIRED_VOTES}** votes • Réagissez avec 👍\n⏰ Expire dans {time_str}",
                inline=False
            )
            await message.edit(embed=embed)

    @app_commands.command(name="dashboardpending", description="Affiche les propositions en attente de validation")
    async def dashboardpending(self, interaction: discord.Interaction):
        try:
            print("[DEBUG] Dashboardpending command called")
            pending = load_pending()
            
            if not pending:
                embed = discord.Embed(
                    title="📭 Aucune proposition",
                    description="Il n'y a pas de tournée en attente de validation",
                    color=discord.Color.greyple()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            await interaction.response.defer()
            
            # Créer les pages avec pagination
            PAGE_CHAR_LIMIT = 5800
            pages = []
            current_embed = discord.Embed(
                title="⏳ Propositions en Attente",
                description=f"*Nécessitent {REQUIRED_VOTES} votes pour être validées*",
                color=discord.Color.orange()
            )
            base_size = len(current_embed.title or "") + len(current_embed.description or "")
            current_page_size = base_size
            
            print(f"[DEBUG] {len(pending)} propositions to display")
            
            pending_count = 0
            for proposal_id, entry in pending.items():
                pending_count += 1
                
                user = await self.bot.fetch_user(entry["user_id"])
                added_by = await self.bot.fetch_user(entry["added_by"])
                emoji = ICONS.get(entry["item"], "❓")
                votes_count = len(entry["votes"])
                
                # Calculer le temps restant avec arrondi à la minute supérieure
                expires_at = datetime.fromisoformat(entry["expires_at"])
                time_left = expires_at - datetime.now()
                total_minutes = math.ceil(time_left.total_seconds() / 60)
                hours_left = total_minutes // 60
                minutes_left = total_minutes % 60
                time_str = f"{hours_left}h{minutes_left}min" if hours_left > 0 else f"{minutes_left}min"
                
                field_name = f"{emoji} {entry['item']} ×{entry['amount']} pour {user.display_name}"
                field_value = f"**Votes :** {votes_count}/{REQUIRED_VOTES}      •      ⏰ {time_str}\n**Par :** {added_by.mention}"
                
                if entry["reason"]:
                    field_value += f"\n**Raison :** *{entry['reason']}*"
                
                # Calculer la taille de ce field
                field_size = len(field_name) + len(field_value)
                
                print(f"[DEBUG] Proposition {pending_count}: {field_size} chars, current page: {current_page_size} chars, {len(current_embed.fields)} fields")
                
                # Vérifier les limites (fields ET caractères)
                will_exceed_fields = (len(current_embed.fields) >= MAX_FIELDS_PER_PAGE)
                will_exceed_chars = (current_page_size + field_size > PAGE_CHAR_LIMIT)
                
                if (will_exceed_fields or will_exceed_chars) and len(current_embed.fields) > 0:
                    print(f"[DEBUG] Pending page full (fields: {will_exceed_fields}, chars: {will_exceed_chars}), creating new page")
                    pages.append(current_embed)
                    current_embed = discord.Embed(
                        title="⏳ Propositions en Attente",
                        description=f"*Nécessitent {REQUIRED_VOTES} votes pour être validées*",
                        color=discord.Color.orange()
                    )
                    current_page_size = base_size
                
                current_embed.add_field(name=field_name, value=field_value, inline=False)
                current_page_size += field_size
            
            # Ajouter la dernière page
            if len(current_embed.fields) > 0:
                pages.append(current_embed)
            
            print(f"[DEBUG] Created {len(pages)} pending pages")
            
            # Envoyer avec ou sans pagination
            if len(pages) == 1:
                pages[0].set_footer(text=f"{len(pending)} proposition(s) en attente")
                await interaction.followup.send(embed=pages[0])
            else:
                view = PendingView(pages, interaction.user)
                pages[0].set_footer(text=f"Page 1/{len(pages)} • {len(pending)} proposition(s) en attente")
                await interaction.followup.send(embed=pages[0], view=view)
            
            print("[DEBUG] Dashboardpending sent successfully")
        
        except Exception as e:
            print(f"[ERROR] Dashboardpending failed: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)
            except:
                print("[ERROR] Could not send error message")

async def setup(bot):
    await bot.add_cog(AddCommand(bot))