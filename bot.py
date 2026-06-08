import os
import random
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from PIL import Image, ImageDraw, ImageFont
import math

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
# WHEEL IMAGE
# --------------------
def create_wheel_image(items, highlight=None, filename="wheel.png"):
    size = 1000

    bg_color = (255, 230, 240)

    dark_pink = (255, 105, 180)
    light_pink = (255, 182, 193)

    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    center = size // 2
    radius = 430

    n = len(items)

    if n == 0:
        return filename

    angle_per = 360 / n

    # draw slices
    for i, item in enumerate(items):
        start = -90 + i * angle_per
        end = start + angle_per

        color = dark_pink if i % 2 == 0 else light_pink

        if item == highlight:
            color = (255, 70, 160)

        draw.pieslice(
            (
                center - radius,
                center - radius,
                center + radius,
                center + radius,
            ),
            start=start,
            end=end,
            fill=color,
            outline=(255, 240, 245),
            width=4,
        )

    # outer ring
    draw.ellipse(
        (
            center - radius,
            center - radius,
            center + radius,
            center + radius,
        ),
        outline=(255, 245, 250),
        width=12,
    )

    # font
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except:
        font = ImageFont.load_default()

    # labels
    for i, item in enumerate(items):
        angle = -90 + (i + 0.5) * angle_per

        text_radius = radius * 0.72

        x = center + math.cos(math.radians(angle)) * text_radius
        y = center + math.sin(math.radians(angle)) * text_radius

        bbox = draw.textbbox((0, 0), item, font=font)

        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        draw.text(
            (x - w / 2, y - h / 2),
            item,
            fill="black",
            font=font,
        )

    # center button
    button_radius = 90

    draw.ellipse(
        (
            center - button_radius,
            center - button_radius,
            center + button_radius,
            center + button_radius,
        ),
        fill="black",
        outline="white",
        width=6,
    )

    try:
        spin_font = ImageFont.truetype("arial.ttf", 42)
    except:
        spin_font = ImageFont.load_default()

    spin_text = "Spin"

    bbox = draw.textbbox((0, 0), spin_text, font=spin_font)

    draw.text(
        (
            center - (bbox[2] - bbox[0]) / 2,
            center - (bbox[3] - bbox[1]) / 2,
        ),
        spin_text,
        fill="white",
        font=spin_font,
    )

    # top pointer
    pointer_y = center - radius - 10

    draw.polygon(
        [
            (center, pointer_y),
            (center - 30, pointer_y - 60),
            (center + 30, pointer_y - 60),
        ],
        fill="white",
        outline="gray",
    )

    img.save(filename)

    return filename

# --------------------
# SPIN ANIMATION
# --------------------
async def spin_animation(interaction, items, winner):
    await interaction.response.send_message("🎡 Spinning wheel...")

    delays = [0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0]

    current = random.choice(items)

    for delay in delays:
        current = random.choice(items)

        img = create_wheel_image(items, highlight=current, filename="spin.png")
        file = discord.File(img)

        await asyncio.sleep(delay)

        await interaction.edit_original_response(
            content=f"🎡 Spinning... **{current}**",
            attachments=[file]
        )

    # FINAL RESULT
    img = create_wheel_image(items, highlight=winner, filename="final.png")
    file = discord.File(img)

    await interaction.edit_original_response(
        content=f"🎉 RESULT: **{winner}**",
        attachments=[file]
    )

# --------------------
# READY
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

@bot.tree.command(name="wheel_spin")
async def wheel_spin(interaction: discord.Interaction, name: str):
    if name not in wheels or not wheels[name]:
        await interaction.response.send_message("Empty wheel")
        return

    items = wheels[name]
    winner = random.choice(items)

    await spin_animation(interaction, items, winner)

@bot.tree.command(name="wheel_reset")
async def wheel_reset(interaction: discord.Interaction, name: str):
    wheels[name] = []
    save_wheels()

    await interaction.response.send_message("🔄 Wheel reset")

@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention}")

# --------------------
# RUN
# --------------------
bot.run(TOKEN)