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
intents.message_content = True

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
def _wheel_font(size):
    for path in (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_slice_label(img, text, center, mid_angle_deg, text_radius, font):
    """Draw label centered on the slice midline, tangential and readable."""
    rad = math.radians(mid_angle_deg)
    x = center + math.cos(rad) * text_radius
    y = center + math.sin(rad) * text_radius

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 8

    label = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill="white")

    # Tangential to the wheel; flip on the bottom so text stays upright.
    rotation = mid_angle_deg + 90
    if 90 < mid_angle_deg % 360 < 270:
        rotation += 180

    rotated = label.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
    img.paste(
        rotated,
        (int(x - rotated.width / 2), int(y - rotated.height / 2)),
        rotated,
    )


def create_wheel_image(items, rotation=0, winner=None, filename="wheel.png"):
    size = 1000
    center = size // 2
    radius = 430

    img = Image.new("RGB", (size, size), (255, 230, 240))
    draw = ImageDraw.Draw(img)

    n = len(items)
    angle_step = 360 / n
    font_size = max(28, min(56, int(520 / n)))
    font = _wheel_font(font_size)
    center_font = _wheel_font(max(22, font_size - 8))

    colors = [
        (255, 105, 180),
        (255, 130, 200),
        (255, 160, 210),
        (255, 120, 190),
    ]

    for i, item in enumerate(items):
        start = -90 + rotation + i * angle_step
        end = start + angle_step

        color = colors[i % len(colors)]
        if winner and item == winner:
            color = (255, 60, 150)

        draw.pieslice(
            (center - radius, center - radius, center + radius, center + radius),
            start=start,
            end=end,
            fill=color,
            outline="white",
            width=5,
        )

        mid_angle = start + angle_step / 2
        _draw_slice_label(img, item, center, mid_angle, radius * 0.62, font)

    # --------------------
    # center button (modern)
    # --------------------
    draw.ellipse(
        (center - 95, center - 95, center + 95, center + 95),
        fill=(20, 20, 20),
        outline="white",
        width=6,
    )

    draw.text(
        (center - 45, center - 20),
        "SPIN",
        fill="white",
        font=center_font,
    )

    # pointer
    draw.polygon(
        [
            (center, center - radius - 10),
            (center - 30, center - radius - 70),
            (center + 30, center - radius - 70),
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
    angle_step = 360 / len(items)

    target_rotation = 360 * 5 + (270 - ((winner_index + 0.5) * angle_step))

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
# FLASK KEEPALIVE
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