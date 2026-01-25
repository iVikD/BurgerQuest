import os
import json
import asyncio
from google import genai
from google.genai import types
from telegram import Bot
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# --- SECRETS (Replace these) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MODEL_ID = 'gemini-2.0-flash' 

if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_KEY]):
    print("❌ ERROR: Missing one or more environment variables.")
    print(f"Token present: {bool(TELEGRAM_TOKEN)}, Chat ID: {bool(CHAT_ID)}, Gemini: {bool(GEMINI_KEY)}")
    sys.exit(1) # Stop the action here

client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = """
Analyze this food-related chat message and image.
Return a ONLY a JSON object with: 
{
  "name": "restaurant name",
  "category": "burger" or "other",
  "rating": 1-10,
  "price": number,
  "is_burger": boolean,
  "comment": "short summary",
  "items": ["list", "of", "items"]
}
"""

def get_gps_location(file_path):
    """Extracts GPS coordinates from image EXIF data."""
    try:
        img = Image.open(file_path)
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
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)
            
            lat = to_deg(gps_info["GPSLatitude"])
            lng = to_deg(gps_info["GPSLongitude"])
            return {"lat": lat, "lng": lng}
    except Exception:
        return None
    return None

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    updates = await bot.get_updates()
    
    # Ensure directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("assets/images", exist_ok=True)

    # Load existing database
    db_path = 'data/meals.json'
    db = json.load(open(db_path)) if os.path.exists(db_path) else []
    processed_ids = {entry.get('msg_id') for entry in db}

    for update in updates:
        msg = update.message
        if not msg or str(msg.chat_id) != TELEGRAM_CHAT_ID or msg.message_id in processed_ids:
            continue

        text = msg.text or msg.caption or "Food photo"
        image_content = None
        local_path = None

        # Get sender info
        user = msg.from_user
        sender_name = user.first_name if user else "Unknown Hunter"

        # Download image if exists
        if msg.photo:
            photo = msg.photo[-1]
            tg_file = await bot.get_file(photo.file_id)
            local_path = f"assets/images/{msg.message_id}.jpg"
            await tg_file.download_to_drive(local_path)
            with open(local_path, 'rb') as f:
                image_content = f.read()

        # Call Gemini
        contents = [text]
        if image_content:
            contents.append(types.Part.from_bytes(data=image_content, mime_type='image/jpeg'))

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
            entry['sender'] = sender_name
            entry['msg_id'] = msg.message_id
            entry['timestamp'] = msg.date.isoformat()
            entry['image_path'] = local_path
            entry['gps'] = get_gps_location(local_path) if local_path else None
            
            db.append(entry)
            print(f"✅ Success: Logged {entry['name']}")
            
        except Exception as e:
            print(f"⚠️ Error processing message {msg.message_id}: {e}")

    # Save final DB
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())