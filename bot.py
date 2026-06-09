from flask import Flask
import threading
import os
import random
import json
import asyncio
import time
import logging
import traceback
import urllib.request
from io import BytesIO
import discord
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot")

from PIL import Image, ImageDraw, ImageFont
import math

SPIN_DURATION = 5.0
SPIN_FRAMES = 12
KEEPALIVE_INTERVAL = int(os.environ.get("KEEPALIVE_INTERVAL", 240))  # 4 min (Render sleeps ~15 min)

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


def _slice_text_limits(text_radius, angle_step, wheel_radius, hub_radius=100):
    """Max tangential and radial space for a label inside one slice."""
    tangential = 2 * text_radius * math.sin(math.radians(angle_step / 2)) * 0.86
    radial_in = text_radius - hub_radius
    radial_out = wheel_radius - text_radius
    radial = 2 * min(radial_in, radial_out) * 0.86
    return tangential, radial


def _label_spans(text, size, mid_angle_deg, stroke):
    """How far the rotated label extends along radial and tangential axes."""
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    font = _wheel_font(size)
    bbox = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
    pad = stroke + 6
    label = Image.new(
        "RGBA",
        (bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(label).text(
        (pad - bbox[0], pad - bbox[1]),
        text,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )
    rotated = label.rotate(-mid_angle_deg, expand=True, resample=Image.Resampling.BICUBIC)
    cos_a, sin_a = abs(math.cos(math.radians(mid_angle_deg))), abs(math.sin(math.radians(mid_angle_deg)))
    radial = rotated.width * cos_a + rotated.height * sin_a
    tangential = rotated.width * sin_a + rotated.height * cos_a
    return radial, tangential


def _fit_slice_font(text, base_size, max_tangential, max_radial, mid_angle_deg):
    """Shrink font until the rotated label fits inside the slice."""
    for size in range(base_size, 10, -1):
        stroke = max(1, size // 20)
        radial, tangential = _label_spans(text, size, mid_angle_deg, stroke)
        if radial <= max_radial and tangential <= max_tangential:
            return _wheel_font(size), stroke
    return _wheel_font(10), 1


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


def _make_unrotated_label(text, mid_angle_deg, base_font_size, text_radius, angle_step, wheel_radius):
    max_tangential, max_radial = _slice_text_limits(text_radius, angle_step, wheel_radius)
    length_factor = max(0.35, min(1.0, 6 / max(len(text), 1)))
    start_size = max(10, int(base_font_size * length_factor))
    font, stroke = _fit_slice_font(text, start_size, max_tangential, max_radial, mid_angle_deg)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
    pad = stroke + 6

    label = Image.new("RGBA", (bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(label).text(
        (pad - bbox[0], pad - bbox[1]),
        text,
        font=font,
        fill="white",
        stroke_width=stroke,
        stroke_fill="black",
    )
    return label


def _build_label_cache(items, text_radius, label_font_size, angle_step, wheel_radius):
    cache = []
    n = len(items)
    for i, item in enumerate(items):
        mid_angle = -90 + i * (360 / n)
        cache.append(_make_unrotated_label(
            item, mid_angle, label_font_size, text_radius, angle_step, wheel_radius
        ))
    return cache


def _paste_slice_label(img, label, center_x, center_y, mid_angle_deg, text_radius, fast=False):
    rad = math.radians(mid_angle_deg)
    x = center_x + math.cos(rad) * text_radius
    y = center_y + math.sin(rad) * text_radius
    resample = Image.Resampling.BILINEAR if fast else Image.Resampling.BICUBIC
    rotated = label.rotate(-mid_angle_deg, expand=True, resample=resample)
    img.paste(
        rotated,
        (int(x - rotated.width / 2), int(y - rotated.height / 2)),
        rotated,
    )


def create_wheel_image(items, rotation=0, winner=None, label_cache=None, fast_resample=False):
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
        if label_cache is not None:
            _paste_slice_label(
                img, label_cache[i], center_x, center_y, mid_angle, text_radius, fast=fast_resample
            )
        else:
            label = _make_unrotated_label(
                item, mid_angle, label_font_size, text_radius, angle_step, radius
            )
            _paste_slice_label(img, label, center_x, center_y, mid_angle, text_radius)

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

    return img


def _image_to_discord_file(img, filename="wheel.png"):
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)

# --------------------
# SPIN ANIMATION
# --------------------
async def spin_animation(interaction, items, winner):
    await interaction.response.send_message("🎡 Spinning wheel...")

    try:
        winner_index = items.index(winner)
        angle_step = 360 / len(items)
        target_rotation = 360 * 5 - winner_index * angle_step

        n = len(items)
        text_radius = 430 * 0.70
        label_font_size = max(40, min(78, int(640 / n)))
        label_cache = _build_label_cache(items, text_radius, label_font_size, angle_step, 430)

        spin_start = time.monotonic()

        for frame in range(SPIN_FRAMES):
            progress = frame / (SPIN_FRAMES - 1)
            rotation = target_rotation * (progress ** 0.6)

            img = create_wheel_image(items, rotation=rotation, label_cache=label_cache, fast_resample=True)
            file = _image_to_discord_file(img)

            await interaction.edit_original_response(
                content="🎡 Spinning...",
                attachments=[file],
            )

            target_elapsed = SPIN_DURATION * (frame + 1) / SPIN_FRAMES
            sleep_for = target_elapsed - (time.monotonic() - spin_start)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        img = create_wheel_image(items, rotation=target_rotation, winner=winner)
        file = _image_to_discord_file(img, filename="winner.png")

        await interaction.edit_original_response(
            content=f"🎉 **Result: {winner}!**",
            attachments=[file],
        )
    except Exception:
        log.exception("Spin failed")
        try:
            await interaction.edit_original_response(content="❌ Spin failed. Please try again.")
        except discord.HTTPException:
            pass

# --------------------
# EVENTS
# --------------------
@bot.event
async def on_ready():
    load_wheels()
    try:
        synced = await bot.tree.sync()
        log.info("Synced %s command(s)", len(synced))
    except Exception:
        log.exception("Command sync failed")
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


@bot.event
async def on_error(event, *args, **kwargs):
    log.exception("Discord event error in %s", event)

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
# FLASK KEEPALIVE (main thread — required for Render)
# --------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running"


@app.route("/health")
def health():
    return {"status": "ok", "discord": str(bot.user) if bot.user else "connecting"}


def run_bot():
    try:
        log.info("Starting Discord bot...")
        bot.run(TOKEN, log_handler=None)
    except Exception:
        log.exception("Discord bot crashed")
        raise


def run_keepalive():
    """Ping our own public URL so Render free tier does not spin down the service."""
    url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("KEEPALIVE_URL")
    if not url:
        log.warning(
            "No RENDER_EXTERNAL_URL or KEEPALIVE_URL — keepalive disabled. "
            "Set KEEPALIVE_URL to your Render app URL (e.g. https://wheelbot.onrender.com)."
        )
        return

    ping_url = url.rstrip("/") + "/health"
    log.info("Keepalive enabled, pinging %s every %ss", ping_url, KEEPALIVE_INTERVAL)
    time.sleep(30)  # let Flask and Discord finish starting

    while True:
        try:
            req = urllib.request.Request(ping_url, headers={"User-Agent": "wheelbot-keepalive"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                log.info("Keepalive ping OK (HTTP %s)", resp.status)
        except Exception as exc:
            log.warning("Keepalive ping failed: %s", exc)
        time.sleep(KEEPALIVE_INTERVAL)


def main():
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=run_keepalive, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    log.info("Starting web server on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
