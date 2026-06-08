import os
import random
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --------------------
# ENV / BOT SETUP
# --------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------
# DATA STORAGE
# --------------------
DATA_FILE = "wheels.json"

wheels = {}

# --------------------
# SAVE / LOAD SYSTEM
# --------------------
def load_wheels():
    global wheels
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            wheels = json.load(f)
    except FileNotFoundError:
        wheels = {}

def save_wheels():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(wheels, f, indent=2)

# --------------------
# BOT READY
# --------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    load_wheels()

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

# --------------------
# CREATE WHEEL
# --------------------
@bot.tree.command(name="wheel_create", description="Create a new wheel")
async def wheel_create(interaction: discord.Interaction, name: str):

    if name in wheels:
        await interaction.response.send_message("Wheel already exists.")
        return

    wheels[name] = []
    save_wheels()

    await interaction.response.send_message(f"🎡 Wheel '{name}' created.")

# --------------------
# ADD ITEM
# --------------------
@bot.tree.command(name="wheel_add", description="Add item to a wheel")
async def wheel_add(interaction: discord.Interaction, name: str, item: str):

    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name].append(item)
    save_wheels()

    await interaction.response.send_message(
        f"➕ Added '{item}' to '{name}'."
    )

# --------------------
# SPIN WHEEL
# --------------------
@bot.tree.command(name="wheel_spin", description="Spin a wheel")
async def wheel_spin(interaction: discord.Interaction, name: str, remove: bool = False):

    if name not in wheels or not wheels[name]:
        await interaction.response.send_message("Wheel is empty or doesn't exist.")
        return

    result = random.choice(wheels[name])

    if remove:
        wheels[name].remove(result)
        save_wheels()

    await interaction.response.send_message(f"🎡 You spun: **{result}**")

# --------------------
# RESET WHEEL
# --------------------
@bot.tree.command(name="wheel_reset", description="Clear all items from a wheel")
async def wheel_reset(interaction: discord.Interaction, name: str):

    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name] = []
    save_wheels()

    await interaction.response.send_message(f"🔄 Wheel '{name}' reset.")

# --------------------
# HELLO TEST
# --------------------
@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hello {interaction.user.mention}!"
    )

# --------------------
# RUN BOT
# --------------------
bot.run(TOKEN)