import os
import random
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --------------------
# LOAD ENV
# --------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("DISCORD_TOKEN is missing in environment variables")

# --------------------
# DISCORD BOT SETUP
# --------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------
# DATA STORAGE
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
# SIMPLE WEB SERVER (RENDER PORT FIX)
# --------------------
def run_web():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

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
# COMMANDS
# --------------------

@bot.tree.command(name="wheel_create", description="Create a new wheel")
async def wheel_create(interaction: discord.Interaction, name: str):
    if name in wheels:
        await interaction.response.send_message("Wheel already exists.")
        return

    wheels[name] = []
    save_wheels()

    await interaction.response.send_message(f"🎡 Wheel '{name}' created.")

@bot.tree.command(name="wheel_add", description="Add item to a wheel")
async def wheel_add(interaction: discord.Interaction, name: str, item: str):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name].append(item)
    save_wheels()

    await interaction.response.send_message(f"➕ Added '{item}' to '{name}'.")

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

@bot.tree.command(name="wheel_reset", description="Reset a wheel")
async def wheel_reset(interaction: discord.Interaction, name: str):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    wheels[name] = []
    save_wheels()

    await interaction.response.send_message(f"🔄 Wheel '{name}' reset.")

@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hello {interaction.user.mention}!"
    )

# --------------------
# RUN BOT
# --------------------
bot.run(TOKEN)