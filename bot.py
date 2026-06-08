from flask import Flask
import threading
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
def create_wheel_image(items, rotation=0, winner=None, filename="wheel.png"):
    size = 1000

    bg_color = (255, 230, 240)

    dark_pink = (255, 105, 180)
    light_pink = (255, 182, 193)

    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    center = size // 2
    radius = 430

    angle_per = 360 / len(items)

    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except:
        font = ImageFont.load_default()

    for i, item in enumerate(items):
        start = -90 + rotation + (i * angle_per)
        end = start + angle_per

        color = dark_pink if i % 2 == 0 else light_pink

        if item == winner:
            color = (255, 60, 150)

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
            outline="white",
            width=4,
        )

        label_angle = start + angle_per / 2

text_radius = radius * 0.72

x = center + math.cos(math.radians(label_angle)) * text_radius
y = center + math.sin(math.radians(label_angle)) * text_radius

bbox = draw.textbbox((0, 0), item, font=font)

tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]

label_img = Image.new(
    "RGBA",
    (tw + 40, th + 40),
    (0, 0, 0, 0)
)

label_draw = ImageDraw.Draw(label_img)

# black outline
for ox in (-2, -1, 0, 1, 2):
    for oy in (-2, -1, 0, 1, 2):
        if ox != 0 or oy != 0:
            label_draw.text(
                (20 + ox, 20 + oy),
                item,
                font=font,
                fill="black"
            )

# white text
label_draw.text(
    (20, 20),
    item,
    font=font,
    fill="white"
)

rotated = label_img.rotate(
    label_angle + 90,
    expand=True,
    resample=Image.BICUBIC
)

img.paste(
    rotated,
    (
        int(x - rotated.width / 2),
        int(y - rotated.height / 2)
    ),
    rotated
)

        

    # center button
    draw.ellipse(
        (
            center - 90,
            center - 90,
            center + 90,
            center + 90,
        ),
        fill="black",
        outline="white",
        width=6,
    )

    draw.text(
        (center - 35, center - 15),
        "SPIN",
        fill="white",
        font=font,
    )

    # POINTER
    pointer_y = center - radius - 15

    draw.polygon(
        [
            (center, pointer_y),
            (center - 35, pointer_y - 70),
            (center + 35, pointer_y - 70),
        ],
        fill="white",
        outline="black",
    )

    img.save(filename)

    return filename

# --------------------
# SPIN ANIMATION
# --------------------
async def spin_animation(interaction, items, winner):
    await interaction.response.send_message("🎡 Spinning wheel...")

    winner_index = items.index(winner)

    angle_per = 360 / len(items)

    target_rotation = (
        360 * 5
        + (270 - ((winner_index + 0.5) * angle_per))
    )

    frames = 20

    for frame in range(frames):
        progress = frame / (frames - 1)

        rotation = target_rotation * (progress ** 0.6)

        img = create_wheel_image(
            items,
            rotation=rotation,
            filename="spin.png"
        )

        file = discord.File(img)

        await interaction.edit_original_response(
            content="🎡 Spinning...",
            attachments=[file]
        )

        await asyncio.sleep(0.12 + progress * 0.08)

    img = create_wheel_image(
        items,
        rotation=target_rotation,
        winner=winner,
        filename="winner.png"
    )

    file = discord.File(img)

    await interaction.edit_original_response(
        content=f"🏆 WINNER: **{winner}**",
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

@bot.tree.command(name="wheel_add_many")
async def wheel_add_many(
    interaction: discord.Interaction,
    name: str,
    items: str
):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    # Split by commas
    new_items = [item.strip() for item in items.split(",") if item.strip()]

    wheels[name].extend(new_items)
    save_wheels()

    await interaction.response.send_message(
        f"➕ Added {len(new_items)} items to **{name}**"
    )

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
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
bot.run(TOKEN)