import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory wheel storage (resets when bot restarts)
wheels = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

# Create wheel
@bot.tree.command(name="wheel_create", description="Create a new wheel")
async def wheel_create(interaction: discord.Interaction, name: str):
    if name in wheels:
        await interaction.response.send_message("Wheel already exists.")
        return

    wheels[name] = []
    await interaction.response.send_message(f"🎡 Wheel '{name}' created.")

# Add item
@bot.tree.command(name="wheel_add", description="Add item to a wheel")
async def wheel_add(interaction: discord.Interaction, name: str, item: str):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name].append(item)
    await interaction.response.send_message(f"➕ Added '{item}' to '{name}'.")

# Spin wheel (optional remove)
@bot.tree.command(name="wheel_spin", description="Spin a wheel")
async def wheel_spin(interaction: discord.Interaction, name: str, remove: bool = False):
    if name not in wheels or len(wheels[name]) == 0:
        await interaction.response.send_message("Wheel is empty or doesn't exist.")
        return

    result = random.choice(wheels[name])

    if remove:
        wheels[name].remove(result)

    await interaction.response.send_message(
        f"🎡 You spun: **{result}**"
    )

# Reset wheel
@bot.tree.command(name="wheel_reset", description="Reset a wheel (clear all items)")
async def wheel_reset(interaction: discord.Interaction, name: str):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name] = []
    await interaction.response.send_message(f"🔄 Wheel '{name}' reset.")

# Simple test command
@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hello {interaction.user.mention}!"
    )

bot.run(TOKEN)