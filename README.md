# Morning Briefing Agent

A personal agent that checks your Gmail, Google Calendar, and Slack, then uses an LLM to synthesize a concise daily briefing — printed to your terminal and DM'd to you on Slack.

## What it does

Each run, the agent:
1. Fetches unread Gmail from the last 12 hours
2. Fetches upcoming Google Calendar events for the next 24 hours
3. Fetches recent activity from your most active Slack channels (last 12 hours)
4. Sends everything to an LLM (via [OpenRouter](https://openrouter.ai)) to produce a briefing with these sections:
   - **URGENT** — anything needing immediate attention
   - **UPCOMING EVENTS** — today's and tomorrow's calendar events
   - **SLACK HIGHLIGHTS** — key discussions from overnight
   - **OTHER EMAILS** — everything else worth knowing
   - **SUGGESTED ACTIONS** — 2–4 concrete next steps
5. Prints the briefing and sends it as a Slack DM to yourself

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/Tatopapi3/morning-briefing-agent.git
cd morning-briefing-agent
python3 -m venv .venv
source .venv/bin/activate
pip install strands-agents strands-agents-tools litellm google-auth google-auth-oauthlib google-api-python-client slack_sdk python-dotenv
```

### 2. OpenRouter API key

Sign up at [openrouter.ai](https://openrouter.ai), create an API key, and add it to a `.env` file in the project root:

```
OPENROUTER_API_KEY=sk-or-...
```

Verify the model works:

```bash
python test_model.py
```

### 3. Google credentials (Gmail + Calendar)

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Gmail API** and **Google Calendar API**
3. Configure the OAuth consent screen (External, Testing mode is fine)
4. Create an OAuth client ID of type **Desktop app**
5. Download the JSON, rename it to `credentials.json`, and place it in the project root

The first time you run `agent.py`, a browser window will open for you to authorize access. A `token.json` is saved afterward so you won't need to log in again until it expires.

### 4. Slack token

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps) → **From scratch**
2. Under **OAuth & Permissions → User Token Scopes**, add:
   - `channels:read`, `channels:history`
   - `groups:read`, `groups:history`
   - `chat:write`, `im:write`
3. Install (or reinstall) the app to your workspace
4. Copy the **User OAuth Token** (`xoxp-...`) into `.env`:

```
SLACK_BOT_TOKEN=xoxp-...
```

## Usage

```bash
cd morning-briefing-agent
source .venv/bin/activate
python agent.py
```

## Files

| File | Purpose |
|---|---|
| `agent.py` | Main agent: Gmail/Calendar/Slack tools + briefing synthesis + Slack DM delivery |
| `test_model.py` | Quick sanity check that the OpenRouter model connection works |
| `.env` | API keys (not committed) |
| `credentials.json` | Google OAuth client config (not committed) |
| `token.json` | Cached Google OAuth token, generated on first run (not committed) |
