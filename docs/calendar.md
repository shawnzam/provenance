# Calendar

Provenance reads your calendar via `icalBuddy` and macOS Calendar. No credentials are stored — it reads the local calendar database that macOS syncs from Exchange/Outlook.

---

## Setup

Install icalBuddy:

```bash
brew install ical-buddy
```

Then add your work account to **System Settings → Internet Accounts** (Exchange or Google). macOS Calendar syncs it in the background. Verify with:

```bash
icalBuddy eventsToday
```

You should see today's events. If not, open macOS Calendar and wait for the sync to complete.

---

## Usage

Calendar access is available in the REPL, via `provenance ask`, and in Claude Desktop.

### REPL / ask

```
P ❯ what's on my calendar today?
P ❯ do I have anything Thursday afternoon?
P ❯ who am I meeting with next week?
P ❯ is there any time free tomorrow morning?
```

### CLI

```bash
provenance ask "what meetings do I have this week?"
```

### Claude Desktop

```
What's on my calendar today?
Prep me for my 2pm — who is Alex and what have we discussed?
```

Claude uses `get_calendar_events` automatically when asked about schedule.

---

## Configuration

Default calendars queried: `Calendar` (Outlook), plus any calendar named after your username. Override in the tool call by passing a `calendars` list.

To see which calendars icalBuddy can see:

```bash
icalBuddy calendars
```

---

## How it works

`get_calendar_events` shells out to `icalBuddy` with a date range and returns structured event data: title, time, location, attendees. icalBuddy reads directly from the local macOS Calendar database.

No API keys, no OAuth, no internet required for calendar access.

---

## Limitations

- macOS only (icalBuddy is a macOS binary)
- Requires an account synced to macOS Calendar — direct Exchange API is not supported
- Calendar data is read-only — Provenance cannot create or modify calendar events
- `icalBuddy` must be on your PATH
