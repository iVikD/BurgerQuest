# BurgerQuest

A personal food-tracking dashboard focused on burger consumption. Send meal photos and descriptions to a Telegram chat, and BurgerQuest automatically extracts structured data using AI and displays it on an interactive dashboard.

## How it works

```
Telegram Chat -> Python Scraper (Gemini AI + EXIF GPS) -> meals.json -> Dashboard
```

1. **Send** meal photos and notes to a Telegram group chat
2. **Scraper** runs daily via GitHub Actions — fetches new messages, analyzes them with Google Gemini 2.0 Flash, extracts GPS from image EXIF data
3. **Dashboard** renders everything client-side: charts, maps, photo galleries, search/filter

## Dashboard features

- Monthly burger battle between participants
- Personal average rating charts
- Category breakdown (burger vs other cuisines)
- Interactive map with meal locations (Leaflet.js + CartoDB dark tiles)
- Photo lightbox gallery with search, filter, and sort
- Separate burger and non-burger galleries
- Participant overlays on meal cards
- Shared meal tracking

## Tech stack

- **Backend**: Python, Google Gemini 2.0 Flash, Telegram Bot API
- **Frontend**: Vanilla JS, Chart.js, Leaflet.js
- **Data**: Single JSON file (`data/meals.json`)
- **CI/CD**: GitHub Actions (daily scrape + auto-commit)
- **Hosting**: GitHub Pages

## Setup

### Prerequisites

- Python 3.10+
- Telegram Bot token + chat ID
- Google Gemini API key

### Run locally

```bash
pip install google-genai python-telegram-bot pillow piexif

export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export GEMINI_KEY="..."
export PARTICIPANT_MAP="Name1:A,Name2:B"

python process_logs.py
```

### View the dashboard

Open `index.html` in a browser or serve it locally:

```bash
python -m http.server
```

## Environment variables

| Variable | Description |
|---|---|
| `TELEGRAM_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Target chat ID |
| `GEMINI_KEY` | Google Gemini API key |
| `PARTICIPANT_MAP` | Name-to-initial mapping (e.g. `"Jaque:J,Victor:V"`) |
