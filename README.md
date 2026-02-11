# Telegram Bot Starter

A modular Telegram bot with pluggable abilities. Clone it, add your token, and go.

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <this-repo>
cd telegram-bot-starter

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — paste your bot token from @BotFather

# 5. Run
python bot.py
```

## Built-in Commands

| Command | What it does |
|---------|-------------|
| `/start` | Show available commands |
| `/scrape <url>` | Fetch a webpage and return cleaned text |
| `/weather <city>` | Current weather (no API key needed) |
| `/remind <min> <msg>` | Set a timed reminder |

## Architecture

```
bot.py              ← Main bot, registers command handlers
abilities/
  scraper.py        ← Web scraping (requests + BeautifulSoup)
  weather.py        ← Weather via Open-Meteo (free, no key)
  reminders.py      ← Delayed messages via job queue
utils/              ← Shared helpers (add your own)
```

**Adding a new ability:**
1. Create `abilities/your_feature.py` with the core logic
2. Import it in `bot.py`
3. Add a `CommandHandler` in `main()`

## Features to Add Next

These are ordered roughly by usefulness and difficulty:

### Easy wins
- **Link preview / summarizer** — `/summarize <url>` that returns title + description + first few paragraphs (the `summarize_page` function in scraper.py already does this, just wire it up)
- **Currency converter** — hit a free FX API, return conversions
- **Unit converter** — temp, distance, weight (pure Python, no API)
- **Dice / random** — `/roll 2d6`, `/flip`, `/pick option1 option2 option3`
- **QR code generator** — `/qr <text>` → generate and send as image using `qrcode` lib

### Medium effort
- **Web search** — `/search <query>` using DuckDuckGo's instant answer API or SearXNG
- **News headlines** — scrape RSS feeds (BBC, Reuters, etc.) and send top 5
- **YouTube download** — `/yt <url>` using `yt-dlp` to grab audio/video and send as file
- **PDF reader** — user sends a PDF, bot extracts text with `pymupdf` and replies
- **Image OCR** — user sends a photo, bot extracts text with `pytesseract`
- **URL monitoring** — watch a URL for changes, alert when content differs
- **Bookmark manager** — save/tag/search URLs with a simple SQLite backend
- **Expense tracker** — `/spent 12.50 lunch` → log to SQLite, `/expenses` → summary

### Advanced
- **AI chat** — pipe messages to OpenAI/Anthropic/Ollama and return responses (conversational mode with context)
- **Scheduled scraping** — cron-like jobs that scrape pages and push updates (price drops, new posts, stock alerts)
- **Multi-step workflows** — conversation handlers for guided flows (e.g., filling out a form step by step)
- **Database backend** — swap from in-memory to SQLite or PostgreSQL for persistence across restarts
- **Webhook mode** — switch from polling to webhooks for production (lower latency, scales better)
- **Admin dashboard** — simple web UI to see bot stats, active users, recent commands
- **Plugin system** — auto-discover abilities from the `abilities/` folder without editing `bot.py`

## Web Scraping Tips

The built-in scraper uses `requests` + `BeautifulSoup` which works for static pages. For JavaScript-heavy sites:

- **Playwright** (`pip install playwright && playwright install`) — headless browser, handles SPAs, login flows, infinite scroll
- **Selenium** — similar to Playwright but older; good if you need Chrome specifically
- **httpx** — async HTTP client, good for scraping many pages concurrently
- **Scrapy** — full scraping framework with pipelines, middleware, rate limiting

### Anti-bot tips
- Rotate user agents
- Add random delays between requests
- Use proxies for volume scraping
- Respect `robots.txt` and rate limits
- Cache results to avoid re-fetching

## Security Notes

- **Always set `ALLOWED_USER_IDS`** in production — without it, anyone who finds your bot can use it
- Never commit `.env` (it's in `.gitignore`)
- Be careful with `/scrape` — it can hit internal network URLs. Consider URL validation if exposing publicly
- Rate-limit commands if deploying publicly to prevent abuse
