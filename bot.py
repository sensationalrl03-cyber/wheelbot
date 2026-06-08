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
intents.message_content = True  # safer for future features

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
# FAST WHEEL RENDERER (FIXED)
# --------------------
def create_wheel_image(items, rotation=0, winner=None, filename="wheel.png"):
    size = 1000
    center = size // 2
    radius = 420

    img = Image.new("RGB", (size, size), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    angle_step = 360 / len(items)

    # ---------- FONT ----------
    try:
        font = ImageFont.truetype("arial.ttf", 44)
        font_small = ImageFont.truetype("arial.ttf", 34)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # ---------- NEON OUTER GLOW ----------
    for r in range(460, 500, 6):
        alpha_color = (255, 60, 180)
        draw.ellipse(
            (center - r, center - r, center + r, center + r),
            outline=alpha_color
        )

    # ---------- WHEEL SEGMENTS ----------
    for i, item in enumerate(items):
        start = -90 + rotation + i * angle_step
        end = start + angle_step

        # neon alternating colors
        base = (255, 40, 160) if i % 2 == 0 else (255, 120, 200)

        if winner and item == winner:
            base = (255, 230, 120)  # highlight winner

        draw.pieslice(
            (center - radius, center - radius, center + radius, center + radius),
            start=start,
            end=end,
            fill=base,
            outline=(255, 255, 255),
            width=4
        )

       # ---------- LABEL (FIXED ALIGNMENT + BIGGER TEXT) ----------
mid_angle = math.radians(start + angle_step / 2)

text_radius = radius * 0.72

x = center + math.cos(mid_angle) * text_radius
y = center + math.sin(mid_angle) * text_radius

# scale font slightly based on slice size (better readability)
font_size = max(34, int(900 / len(items)))
try:
    font_dynamic = ImageFont.truetype("arial.ttf", font_size)
except:
    font_dynamic = ImageFont.load_default()

txt = Image.new("RGBA", (400, 150), (0, 0, 0, 0))
tdraw = ImageDraw.Draw(txt)

tdraw.text(
    (200, 75),
    item,
    fill="white",
    anchor="mm",
    font=font_dynamic
)

# IMPORTANT: correct rotation direction fix
rotated = txt.rotate(
    -math.degrees(mid_angle) + 90,
    resample=Image.BICUBIC,
    expand=True
)

img.paste(
    rotated,
    (int(x - rotated.size[0] / 2), int(y - rotated.size[1] / 2)),
    rotated
)

    # ---------- INNER RING ----------
    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        outline=(255, 255, 255),
        width=6
    )

    # ---------- CENTER BUTTON (GLOSSY STYLE) ----------
    for r in range(90, 60, -4):
        draw.ellipse(
            (center - r, center - r, center + r, center + r),
            fill=(10, 10, 15)
        )

    draw.ellipse(
        (center - 70, center - 70, center + 70, center + 70),
        outline=(255, 255, 255),
        width=3
    )

    draw.text(
        (center, center),
        "SPIN",
        fill="white",
        anchor="mm",
        font=font
    )

    # ---------- POINTER ----------
    draw.polygon(
        [
            (center, center - radius - 20),
            (center - 25, center - radius - 70),
            (center + 25, center - radius - 70),
        ],
        fill="white"
    )

    img.save(filename)
    return filename

# --------------------
# SPIN ANIMATION
# --------------------
async def spin_animation(interaction, items, winner):
    await interaction.response.send_message("🎡 Spinning wheel...")

    winner_index = items.index(winner)
    angle_step = 360 / len(items)

    pointer_angle = 0  # top in math coords

target_rotation = (
    360 * 5
    - (winner_index * angle_step)
    - (angle_step / 2)
)

    frames = 20

    for frame in range(frames):
        progress = frame / (frames - 1)
        rotation = target_rotation * (progress ** 0.6)

        img = create_wheel_image(items, rotation=rotation)
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
# EVENTS
# --------------------
@bot.event
async def on_ready():
    load_wheels()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

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
async def wheel_add_many(interaction: discord.Interaction, name: str, items: str):
    if name not in wheels:
        await interaction.response.send_message("Wheel not found.")
        return

    new_items = [i.strip() for i in items.split(",") if i.strip()]
    wheels[name].extend(new_items)
    save_wheels()

    await interaction.response.send_message(f"➕ Added {len(new_items)} items")

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
# FLASK + BOT
# --------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

threading.Thread(target=run_web, daemon=True).start()

bot.run(TOKEN)