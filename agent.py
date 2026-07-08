import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def get_google_credentials():
    # Serverless path (e.g. Vercel): rebuild credentials from env vars and
    # refresh in-memory. There's no browser and no writable token.json there.
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    if refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds

    # Local dev path: interactive browser flow, cached in token.json.
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


@tool
def check_gmail(hours_back: int = 12) -> str:
    """Fetch unread emails from Gmail from the last N hours."""
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)
        after = int((datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp())
        results = service.users().messages().list(
            userId="me",
            q=f"is:unread after:{after}",
            maxResults=20,
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No unread emails in the last {} hours.".format(hours_back)
        emails = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            snippet = detail.get("snippet", "")[:200]
            emails.append(
                f"From: {headers.get('From', '?')}\n"
                f"Subject: {headers.get('Subject', '?')}\n"
                f"Date: {headers.get('Date', '?')}\n"
                f"Snippet: {snippet}"
            )
        return "\n\n".join(emails)
    except Exception as e:
        return f"Gmail error: {e}"


@tool
def check_calendar(hours_ahead: int = 24) -> str:
    """Fetch upcoming Google Calendar events for the next N hours."""
    try:
        creds = get_google_credentials()
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(hours=hours_ahead)
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return f"No events in the next {hours_ahead} hours."
        out = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", "?"))
            end = e["end"].get("dateTime", e["end"].get("date", "?"))
            attendees = ", ".join(
                a.get("email", "") for a in e.get("attendees", [])
            ) or "none"
            out.append(
                f"Title: {e.get('summary', 'Untitled')}\n"
                f"Start: {start}\nEnd: {end}\n"
                f"Location: {e.get('location', 'none')}\n"
                f"Attendees: {attendees}"
            )
        return "\n\n".join(out)
    except Exception as e:
        return f"Calendar error: {e}"


@tool
def check_slack(hours_back: int = 12, max_channels: int = 5) -> str:
    """Fetch recent Slack messages from the most active channels."""
    try:
        client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        oldest = str((datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp())
        channels_resp = client.conversations_list(types="public_channel,private_channel", limit=200)
        channels = channels_resp.get("channels", [])
        active = []
        for ch in channels:
            if not ch.get("is_member"):
                continue
            try:
                hist = client.conversations_history(
                    channel=ch["id"], oldest=oldest, limit=1
                )
                msgs = hist.get("messages", [])
                if msgs:
                    active.append((float(msgs[0].get("ts", 0)), ch))
            except SlackApiError:
                continue
        active.sort(reverse=True)
        top = active[:max_channels]
        if not top:
            return f"No Slack activity in the last {hours_back} hours."
        out = []
        for _, ch in top:
            hist = client.conversations_history(
                channel=ch["id"], oldest=oldest, limit=5
            )
            msgs = hist.get("messages", [])
            lines = [f"#{ch['name']}:"]
            for m in msgs:
                text = m.get("text", "")[:200]
                lines.append(f"  - {text}")
            out.append("\n".join(lines))
        return "\n\n".join(out)
    except Exception as e:
        return f"Slack error: {e}"


def send_slack_dm(text: str) -> None:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    user_id = client.auth_test()["user_id"]
    im = client.conversations_open(users=[user_id])
    channel_id = im["channel"]["id"]
    client.chat_postMessage(channel=channel_id, text=text)


SYSTEM_PROMPT = """You are a personal morning briefing assistant.

Always call all three tools in this order:
1. check_gmail (hours_back=12)
2. check_calendar (hours_ahead=24)
3. check_slack (hours_back=12)

After collecting all data, synthesize a concise briefing with these exact sections:

URGENT
List emails or messages that need immediate attention today.

UPCOMING EVENTS
List today's and tomorrow's calendar events with times.

SLACK HIGHLIGHTS
Key discussions or decisions from overnight Slack activity.

OTHER EMAILS
Everything else worth knowing from Gmail, briefly.

SUGGESTED ACTIONS
2–4 concrete next steps based on everything above.

Be concise. Use bullet points. Skip empty sections."""


def run():
    model = LiteLLMModel(
        client_args={
            "api_base": "https://openrouter.ai/api/v1",
            "api_key": os.environ["OPENROUTER_API_KEY"],
        },
        model_id="openrouter/openrouter/free",
        params={"max_tokens": 4096},
    )
    agent = Agent(
        model=model,
        tools=[check_gmail, check_calendar, check_slack],
        system_prompt=SYSTEM_PROMPT,
    )
    response = agent("What did I miss? Give me my morning briefing.")
    print(response)
    send_slack_dm(str(response))
    return str(response)


if __name__ == "__main__":
    run()
