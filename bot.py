import os
import random
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

import matplotlib.pyplot as plt
import numpy as np

# --------------------
# ENV
# --------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("Missing DISCORD_TOKEN")

# --------------------
# BOT SETUP
# --------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------
# DATA
# --------------------
DATA_FILE = "wheels.json"
wheels = {}

def load_wheels():
    global wheels
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            wheels = json.load(f)
    except:
        wheels = {}

def save_wheels():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(wheels, f, indent=2)

# --------------------
# WHEEL IMAGE
# --------------------
def create_wheel_image(items, winner, filename="wheel.png"):
    colors = plt.cm.tab20(np.linspace(0, 1, len(items)))
    explode = [0.1 if item == winner else 0 for item in items]

    fig, ax = plt.subplots()
    ax.pie(
        [1] * len(items),
        labels=items,
        colors=colors,
        startangle=90,
        explode=explode
    )

    plt.title("Wheel Result")
    plt.savefig(filename)
    plt.close()

    return filename

# --------------------
# READY EVENT
# --------------------
@bot.event
async def on_ready():
    load_wheels()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    print("Commands synced")

# --------------------
# COMMANDS
# --------------------
@bot.tree.command(name="wheel_create")
async def wheel_create(interaction: discord.Interaction, name: str):
    if name in wheels:
        await interaction.response.send_message("Wheel already exists.")
        return

    wheels[name] = []
    save_wheels()

    await interaction.response.send_message(f"🎡 Wheel '{name}' created.")

@bot.tree.command(name="wheel_add")
async def wheel_add(interaction: discord.Interaction, name: str, item: str):
    wheels.setdefault(name, []).append(item)
    save_wheels()

    await interaction.response.send_message(f"➕ Added **{item}**")

# --------------------
# SPIN (WITH IMAGE + SIMPLE ANIMATION)
# --------------------
@bot.tree.command(name="wheel_spin")
async def wheel_spin(interaction: discord.Interaction, name: str):
    if name not in wheels or not wheels[name]:
        await interaction.response.send_message("Empty wheel")
        return

    items = wheels[name]
    winner = random.choice(items)

    # quick "spin feel"
    msg = await interaction.response.send_message("🎡 Spinning...")

    await discord.utils.sleep_until(discord.utils.utcnow())  # tiny safe yield

    img_path = create_wheel_image(items, winner)
    file = discord.File(img_path)

    await interaction.edit_original_response(
        content=f"🎉 Result: **{winner}**",
        attachments=[file]
    )

# --------------------
# RESET
# --------------------
@bot.tree.command(name="wheel_reset")
async def wheel_reset(interaction: discord.Interaction, name: str):
    wheels[name] = []
    save_wheels()
    await interaction.response.send_message("🔄 Wheel reset")

# --------------------
# HELLO
# --------------------
@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention}")

# --------------------
# RUN BOT (IMPORTANT FOR RENDER)
# --------------------
bot.run(TOKEN)