# Telegram Bot + Admin Dashboard

A Telegram bot with an orchestrator that manages multiple agents and a web dashboard to monitor and control them. Zero cloud dependencies — runs on SQLite locally.

## Quick Start

```bash
git clone https://github.com/HJK6/telegram-bot-starter.git
cd telegram-bot-starter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste your bot token from @BotFather
python bot.py
```

Bot starts polling Telegram. Dashboard starts at `http://localhost:8080`.

## Architecture

```
┌───────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Telegram    │◄────►│   bot.py          │◄────►│ orchestrator │
│   (user)      │      │   commands +      │      │   routing +  │
│               │      │   message handler │      │   lifecycle  │
└───────────────┘      └──────────────────┘      └──────┬───────┘
                                                        │
┌───────────────┐      ┌──────────────────┐             │
│   Browser     │◄────►│   dashboard.py   │◄────────────┘
│   (admin)     │      │   Flask web UI   │
└───────────────┘      └──────────────────┘
                                │
                       ┌────────▼────────┐
                       │   store.py      │
                       │   SQLite DB     │
                       └─────────────────┘
```

### Files

| File | Purpose |
|------|---------|
| `bot.py` | Entry point. Telegram handlers + starts dashboard thread |
| `orchestrator.py` | Agent management, message routing (6-level strategy), dashboard commands |
| `dashboard.py` | Flask web UI + REST API for agent control |
| `store.py` | SQLite persistence — agents, chat, logs |
| `models.py` | Data models (Agent, LogEntry, ChatMessage) |
| `config.py` | Configuration from `.env` |
| `templates/` | Dashboard HTML (dark theme, no build step) |

## Telegram Commands

| Command | What it does |
|---------|-------------|
| `/start`, `/help` | Show commands |
| `/status` | Active agents and their current tasks |
| `/agents` | List all agents with IDs |
| `/new <goal>` | Create a new agent |
| `/stop <id>` | Stop an agent (8-char prefix) |
| `/delete <id>` | Delete an agent and its data |
| `/reset` | Stop all agents |
| *(plain text)* | Routed to the best-matching agent automatically |

## Message Routing

When you send a plain message, the orchestrator decides which agent gets it:

1. **"New agent/task" keywords** → creates a new agent
2. **Agent ID prefix** → `a1b2c3d4 do this` routes to that agent
3. **[Title] notation** → `[My Agent] do this` routes by title
4. **Title in text** → mentions an agent's title
5. **Follow-up heuristic** → short replies ("yes", "ok") go to the single active agent
6. **Keyword scoring** → matches words against agent goals/tasks
7. **Fallback** → last agent that sent a message, or creates a new one

## Admin Dashboard

The dashboard runs alongside the bot at `http://localhost:8080` and provides:

- **Overview page** — all agents with status badges, uptime, current task
- **Agent detail** — full chat history, logs, send messages
- **Controls** — create, stop, delete agents from the browser
- **REST API** — programmatic access at `/api/agents`, `/api/agents/<id>/chat`, etc.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Create agent `{"goal": "...", "title": "..."}` |
| GET | `/api/agents/<id>` | Get agent details |
| POST | `/api/agents/<id>/stop` | Stop an agent |
| POST | `/api/agents/<id>/delete` | Delete an agent |
| POST | `/api/agents/<id>/send` | Send message `{"message": "..."}` |
| GET | `/api/agents/<id>/chat` | Get chat history |
| GET | `/api/agents/<id>/logs` | Get agent logs |

## How It Works

Each agent runs `claude -p` (Claude Code CLI) as a subprocess. When a message comes in:

1. The orchestrator routes it to the right agent (or creates a new one)
2. A prompt is built from the agent's goal + conversation history
3. `claude -p --output-format stream-json` runs and returns a response
4. The response is sent back to Telegram and logged in the dashboard

**Prerequisite:** [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) must be installed:
```bash
npm install -g @anthropic-ai/claude-code
```

## Extending

**Add a new Telegram command:**
1. Write a handler function in `bot.py`
2. Register it with `app.add_handler(CommandHandler("name", handler))`

**Add a dashboard page:**
1. Create a template in `templates/`
2. Add a route in `dashboard.py`

**Swap SQLite for Postgres/DynamoDB:**
Replace the functions in `store.py` — the interface is simple: `save_agent`, `get_agent`, `add_log`, `add_chat`, etc.

## Security

- Set `OWNER_CHAT_ID` in `.env` to lock the bot to your Telegram account
- Change `DASHBOARD_SECRET` in production
- The dashboard has no auth by default — add Flask-Login or put it behind a reverse proxy with auth
- Never commit `.env`
