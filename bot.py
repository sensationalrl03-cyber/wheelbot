import os
import random
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --------------------
# ENV
# --------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("Missing DISCORD_TOKEN")

# --------------------
# DISCORD BOT
# --------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

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
# PORT FIX (CRITICAL)
# --------------------
def run_web():
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# --------------------
# BOT READY
# --------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    load_wheels()
    await bot.tree.sync()
    print("Synced commands")

# --------------------
# COMMANDS
# --------------------
@bot.tree.command(name="wheel_create")
async def wheel_create(interaction: discord.Interaction, name: str):
    if name in wheels:
        await interaction.response.send_message("Already exists")
        return
    wheels[name] = []
    save_wheels()
    await interaction.response.send_message("Created wheel")

@bot.tree.command(name="wheel_add")
async def wheel_add(interaction: discord.Interaction, name: str, item: str):
    wheels.setdefault(name, []).append(item)
    save_wheels()
    await interaction.response.send_message("Added")

@bot.tree.command(name="wheel_spin")
async def wheel_spin(interaction: discord.Interaction, name: str):
    if name not in wheels or not wheels[name]:
        await interaction.response.send_message("Empty wheel")
        return
    await interaction.response.send_message(random.choice(wheels[name]))

# --------------------
# RUN
# --------------------
bot.run(TOKEN)