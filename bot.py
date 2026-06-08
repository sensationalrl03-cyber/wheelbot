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


def _fit_slice_font(text, base_size, max_width):
    """Shrink font until the label fits inside the slice arc."""
    for size in range(base_size, 20, -2):
        font = _wheel_font(size)
        measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = measure.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _wheel_font(20)


def _draw_winner_banner(draw, width, height, winner):
    font = _wheel_font(46)
    stroke = 3
    prefix, suffix = "Result: ", "!"
    full = f"{prefix}{winner}{suffix}"

    full_bbox = draw.textbbox((0, 0), full, font=font, stroke_width=stroke)
    prefix_bbox = draw.textbbox((0, 0), prefix, font=font, stroke_width=stroke)
    winner_bbox = draw.textbbox((0, 0), winner, font=font, stroke_width=stroke)
    full_w = full_bbox[2] - full_bbox[0]
    full_h = full_bbox[3] - full_bbox[1]
    pad_x, pad_y = 30, 16
    box_w = full_w + pad_x * 2
    box_h = full_h + pad_y * 2
    box_x = (width - box_w) / 2
    box_y = (height - box_h) / 2

    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=18,
        fill=(30, 30, 30),
        outline="white",
        width=4,
    )

    text_x = box_x + pad_x - full_bbox[0]
    text_y = box_y + pad_y - full_bbox[1]
    draw.text(
        (text_x, text_y),
        prefix,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )

    winner_x = text_x + prefix_bbox[2] - prefix_bbox[0]
    winner_w = winner_bbox[2] - winner_bbox[0]
    winner_h = winner_bbox[3] - winner_bbox[1]
    highlight_pad = 8
    draw.rounded_rectangle(
        (
            winner_x - highlight_pad,
            text_y + winner_bbox[1] - highlight_pad,
            winner_x + winner_w + highlight_pad,
            text_y + winner_bbox[3] + highlight_pad,
        ),
        radius=10,
        fill=(255, 60, 150),
    )
    draw.text(
        (winner_x, text_y),
        winner,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )

    suffix_x = winner_x + winner_w
    draw.text(
        (suffix_x, text_y),
        suffix,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )


def _draw_slice_label(img, text, center_x, center_y, mid_angle_deg, text_radius, base_font_size, angle_step):
    """Bold white label with black outline, rotated to follow the slice radius."""
    rad = math.radians(mid_angle_deg)
    x = center_x + math.cos(rad) * text_radius
    y = center_y + math.sin(rad) * text_radius

    arc_width = 2 * text_radius * math.sin(math.radians(angle_step / 2)) * 0.90
    font = _fit_slice_font(text, base_font_size, arc_width)
    stroke = max(2, base_font_size // 18)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
    pad = stroke + 6

    label = Image.new("RGBA", (bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.text(
        (pad - bbox[0], pad - bbox[1]),
        text,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )

    # Rotate so text runs along the slice (vertical at top, horizontal at sides).
    rotated = label.rotate(-mid_angle_deg, expand=True, resample=Image.Resampling.BICUBIC)
    img.paste(
        rotated,
        (int(x - rotated.width / 2), int(y - rotated.height / 2)),
        rotated,
    )


def create_wheel_image(items, rotation=0, winner=None, filename="wheel.png"):
    wheel_size = 1000
    banner_h = 130 if winner else 0
    radius = 430
    center_x = wheel_size // 2
    center_y = banner_h + wheel_size // 2

    img = Image.new("RGB", (wheel_size, wheel_size + banner_h), (255, 230, 240))
    draw = ImageDraw.Draw(img)

    if winner:
        _draw_winner_banner(draw, wheel_size, banner_h, winner)

    n = len(items)
    angle_step = 360 / n
    label_font_size = max(40, min(78, int(640 / n)))
    center_font = _wheel_font(36)
    text_radius = radius * 0.70

    colors = [
        (255, 105, 180),
        (255, 130, 200),
        (255, 160, 210),
        (255, 120, 190),
    ]

    for i, item in enumerate(items):
        # Offset by half a slice so item 0 sits centered under the top pointer.
        start = -90 - angle_step / 2 + rotation + i * angle_step
        end = start + angle_step

        color = colors[i % len(colors)]
        if winner and item == winner:
            color = (255, 60, 150)

        draw.pieslice(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            start=start,
            end=end,
            fill=color,
            outline="white",
            width=5,
        )

        mid_angle = start + angle_step / 2
        _draw_slice_label(
            img, item, center_x, center_y, mid_angle, text_radius, label_font_size, angle_step
        )

    draw.ellipse(
        (center_x - 95, center_y - 95, center_x + 95, center_y + 95),
        fill=(20, 20, 20),
        outline="white",
        width=6,
    )

    spin_bbox = draw.textbbox((0, 0), "SPIN", font=center_font, stroke_width=2)
    spin_w = spin_bbox[2] - spin_bbox[0]
    spin_h = spin_bbox[3] - spin_bbox[1]
    draw.text(
        (center_x - spin_w / 2, center_y - spin_h / 2),
        "SPIN",
        fill="white",
        font=center_font,
        stroke_width=2,
        stroke_fill="black",
    )

    draw.polygon(
        [
            (center_x, center_y - radius - 10),
            (center_x - 30, center_y - radius - 70),
            (center_x + 30, center_y - radius - 70),
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

    target_rotation = 360 * 5 - winner_index * angle_step

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
        content=f"🎉 **Result: {winner}!**",
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