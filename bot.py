# bot.py

import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True 
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot connecté comme : {bot.user}")
    synced = await bot.tree.sync()
    print(f"Slash commands synchronisées : {len(synced)}")

async def main():
    async with bot:
        await bot.load_extension("add_command")
        await bot.load_extension("dashboard_command")
        await bot.start(TOKEN)

asyncio.run(main())