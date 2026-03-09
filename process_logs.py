import os
import json
import asyncio
import sys
from datetime import datetime
from google import genai
from google.genai import types
from telegram import Bot
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = 'gemini-2.0-flash'
STATE_PATH = 'data/scraper_state.json'

# Map short/nickname forms to canonical names. Update when new users join.
NAME_MAP = {"Jaque": "Jaqueline"}

# Valid participant names. Gemini-returned names not in this set are filtered out.
VALID_NAMES = {"Victor", "Jaqueline"}

if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_KEY]):
    print("❌ ERROR: Missing one or more environment variables.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = """
Analyze this food-related chat message and image(s).
Return ONLY a JSON object with:
{
  "name": "restaurant name",
  "category": "burger" or "other",
  "rating": 1-5,
  "price": total price paid for the entire order in EUR (not per-person),
  "is_burger": boolean,
  "comment": "short summary",
  "items": ["list", "of", "items"],
  "participants": ["list", "of", "people", "who", "ate"]
}
If the message or context implies the meal was shared (e.g., "we", "us", "together", or naming multiple people), include all of them in "participants".
The "price" should always be the TOTAL bill amount, not the per-person split.
"""


def get_gps_location(file_path):
    """Extracts GPS coordinates from image EXIF data."""
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif()
            if not exif_data: return None
            gps_info = {}
            for tag, value in exif_data.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    for t in value:
                        sub_tag = GPSTAGS.get(t, t)
                        gps_info[sub_tag] = value[t]
            if "GPSLatitude" in gps_info:
                def to_deg(value):
                    d = float(value[0]); m = float(
                        value[1]); s = float(value[2])
                    return d + (m / 60.0) + (s / 3600.0)
                lat = to_deg(gps_info["GPSLatitude"])
                lng = to_deg(gps_info["GPSLongitude"])
                if gps_info.get("GPSLatitudeRef") == "S": lat = -lat
                if gps_info.get("GPSLongitudeRef") == "W": lng = -lng
                return {"lat": lat, "lng": lng}
    except Exception as e:
        print(f"⚠️ Warning: Could not extract GPS from {file_path}: {e}")
        return None
    return None


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state):
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)


async def main():
    print("Starting scraper...")
    bot = Bot(token=TELEGRAM_TOKEN)

    state = load_state()
    last_update_id = state.get('last_update_id')
    offset = last_update_id + 1 if last_update_id else None
    updates = await bot.get_updates(offset=offset)
    print(f"DEBUG: Found {len(updates)} updates from Telegram.")

    os.makedirs("data", exist_ok=True)
    os.makedirs("assets/images", exist_ok=True)

    db_path = 'data/meals.json'
    # Fail-safe loading
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                db = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Warning: Could not load {db_path}, starting fresh: {e}")
            db = []
    else: db = []

    # Build processed IDs from both legacy msg_id and new msg_ids list
    processed_ids = set()
    for entry in db:
        if 'msg_ids' in entry:
            processed_ids.update(entry['msg_ids'])
        if 'msg_id' in entry:
            processed_ids.add(entry['msg_id'])

    # --- BUFFERING LOGIC ---
    # Group messages by media_group_id to save Gemini costs
    groups = {}

    for update in updates:
        msg = update.message
        if not msg or str(msg.chat_id) != TELEGRAM_CHAT_ID or msg.message_id in processed_ids:
            continue

        # Unique key for grouping: media_group_id or just message_id for singles
        group_id = msg.media_group_id if msg.media_group_id else f"single_{msg.message_id}"

        if group_id not in groups:
            groups[group_id] = {"msgs": [], "paths": []}
        groups[group_id]["msgs"].append(msg)

    for group_id, data in groups.items():
        main_msg = data["msgs"][0]
        #Only take the first part of the name
        full_name = main_msg.from_user.first_name if main_msg.from_user else "Unknown Hunter"
        sender = full_name.split()[0]
        sender = NAME_MAP.get(sender, sender)

        # Extract full text from all messages in group
        combined_text = " ".join(
            filter(None, [m.text or m.caption for m in data["msgs"]])) or "Food photo"

        # Download all photos in the group
        for m in data["msgs"]:
            if m.photo:
                photo = m.photo[-1]
                tg_file = await bot.get_file(photo.file_id)
                path = f"assets/images/{photo.file_unique_id}.jpg"
                await tg_file.download_to_drive(path)
                data["paths"].append(path)

        # Call Gemini with all photos at once
        contents = [combined_text]
        opened_images = []
        for p in data["paths"]:
            img = Image.open(p)
            opened_images.append(img)
            contents.append(img)

        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type='application/json'
                )
            )

            entry = json.loads(response.text)

            # Ensure sender is always in participants if Gemini missed it
            if 'participants' not in entry or not isinstance(entry['participants'], list):
                entry['participants'] = [sender]
            elif sender not in entry['participants']:
                entry['participants'].append(sender)

            # Normalize participant names and filter out hallucinations
            entry['participants'] = [NAME_MAP.get(p, p) for p in entry['participants']]
            entry['participants'] = [p for p in entry['participants'] if p in VALID_NAMES]
            if sender not in entry['participants']:
                entry['participants'].append(sender)

            entry['sender'] = sender
            entry['msg_id'] = main_msg.message_id
            entry['msg_ids'] = [m.message_id for m in data["msgs"]]
            entry['timestamp'] = main_msg.date.isoformat()
            # Store all paths for the dashboard gallery
            entry['image_paths'] = data["paths"]
            # Primary image for the cover
            entry['image_path'] = data["paths"][0] if data["paths"] else None
            # GPS from the first photo
            entry['gps'] = get_gps_location(
                data["paths"][0]) if data["paths"] else None

            db.append(entry)
            print(f"✅ Success: Logged {entry['name']} from {sender}")

        except Exception as e:
            print(f"⚠️ Error processing group {group_id}: {e}")
        finally:
            for img in opened_images:
                img.close()

    # Save final DB
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2)

    # Persist Telegram offset for next run
    if updates:
        state['last_update_id'] = max(u.update_id for u in updates)
        save_state(state)

if __name__ == "__main__":
    asyncio.run(main())
