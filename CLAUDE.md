# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BurgerQuest is a personal food-tracking dashboard focused on burger consumption. Users send meal photos and descriptions to a Telegram chat. A Python scraper (scheduled daily via GitHub Actions) fetches those messages, analyzes them with Google Gemini 2.0 Flash, extracts GPS from image EXIF, and stores structured data in `data/meals.json`. A single-page HTML dashboard (`index.html`) renders interactive charts, maps, and galleries from that JSON file.

## Architecture

```
Telegram Chat → process_logs.py (Gemini AI + EXIF GPS) → data/meals.json → index.html dashboard
```

- **process_logs.py** — Async Python script that connects to Telegram Bot API, groups media messages to minimize Gemini calls, downloads photos to `assets/images/`, calls Gemini for structured extraction, and appends entries to the JSON database.
- **index.html** — Vanilla JS single-page app (no framework). Uses Chart.js for visualizations, Leaflet.js with OpenStreetMap/CartoDB for maps. Loads all data client-side from `data/meals.json`.
- **data/meals.json** — Flat JSON array, the single source of truth. Each entry has: name, category, rating (1-5), price (EUR), is_burger, comment, items, participants, sender, msg_id, timestamp, image_path, image_paths, gps.
- **GitHub Actions** (`.github/workflows/daily_scrape.yml`) — Runs `process_logs.py` daily at midnight UTC and auto-commits changes. Can also be triggered manually.

## Commands

### Run the scraper locally
```bash
export TELEGRAM_TOKEN="..." TELEGRAM_CHAT_ID="..." GEMINI_KEY="..."
pip install google-genai python-telegram-bot pillow piexif
python process_logs.py
```

### View the dashboard
Open `index.html` directly in a browser or use a local server (`python -m http.server`).

### No build step, no test suite, no linter configured.

## Environment Variables (required for scraper)

- `TELEGRAM_TOKEN` — Telegram Bot API token
- `TELEGRAM_CHAT_ID` — Target chat ID
- `GEMINI_KEY` — Google Gemini API key

These are stored as GitHub Actions secrets for the CI pipeline.

## Key Conventions

- **Participants**: Meals can be shared. The sender is always included in the participants list (enforced in `process_logs.py`). Burger counts are per-participant.
- **Media grouping**: Multiple photos in a Telegram media group are processed as a single Gemini call to reduce API costs.
- **GPS**: Extracted from EXIF on the first photo of each group. Some entries have manually-added GPS.
- **Auto-commits**: The GitHub Actions bot commits with message "Auto-update food logs". Manual commits use descriptive messages.
- **No `.gitignore`**: Be careful not to commit `.env` files or API keys.
