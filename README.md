# caller_app

A small Python app that **places outbound phone calls** and runs a real-time **worried-citizen** conversation (illegal parking report) using an **ElevenLabs Conversational AI agent** over **Twilio Media Streams**.

This README is written so you can set it up, run it, and understand what each piece does.

---

## What the app does (big picture)

1. You keep a list of people in a spreadsheet file (`data/contacts.csv`).
2. When you run the caller script, it calls the contact you name with **`--contact`** or **`CALL_CONTACT` in `.env`**.
3. It asks **Twilio** to ring that person.
4. When they pick up, Twilio opens a **two-way WebSocket** to your Python server and streams the call audio in both directions.
5. Your server bridges that audio to an **ElevenLabs Conversational AI agent** (STT + LLM + TTS in one pipeline).
6. The agent talks with the person in real time — barge-in supported — and your server passes the audio straight back to Twilio.
7. The call ends when the agent says goodbye (or the person hangs up).

You trigger calls manually — nothing runs on a schedule yet.

---

## The parts (what each thing is for)

| Part | What it is | What it does in this app |
|------|------------|--------------------------|
| **`data/contacts.csv`** | A simple contact list | Names, phones, language; pick who to call with `--contact` or `CALL_CONTACT` |
| **`run_calls.py`** | A short Python script you run by hand | Finds the active contact and tells Twilio to start calling |
| **`app/main.py`** | FastAPI web server | Handles `/voice/inbound` webhook and the `/media-stream` WebSocket |
| **`app/twilio_audio_interface.py`** | Audio bridge | Forwards μ-law 8 kHz audio between Twilio and ElevenLabs |
| **`app/csv_store.py`** | CSV reader | Loads contacts and checks call schedule |
| **`app/twilio_client.py`** | Twilio helper | Builds the API client, watches call status, ring timeout |
| **`.env`** | Secret config file (not in git) | API keys, agent ID, phone number, public URL |
| **Twilio** | Cloud phone service | Places calls and ships audio over a WebSocket (Media Streams) |
| **ElevenLabs Conversational AI** | Real-time voice agent | Streams STT + LLM + TTS as a single low-latency pipeline |
| **ngrok** | Tunnel tool | Gives your laptop a public URL so Twilio can reach your local server |
| **uvicorn** | Web server runner | Keeps `app/main.py` listening (default port **8001** — avoids ComfyUI on 8000) |

Think of it like this:

```
You → run_calls.py → Twilio API → person's phone (ringing)
                                       ↓ (when answered)
                       Twilio  ←──── Media Stream WebSocket ────→  your FastAPI
                                                                       ↕  WebSocket
                                                       ElevenLabs Conversational AI agent
```

All audio flows over WebSockets — no MP3 files, no `<Gather>`/`<Play>` round-trips. Twilio uses μ-law 8 kHz audio; the app transcodes to/from the agent's PCM 16 kHz audio so the phone hears clean speech instead of static.

---

## What happens during one call (step by step)

| Step | Who does it | What happens |
|------|-------------|--------------|
| 1 | **You** run `python run_calls.py --contact Marina` | Script looks up that name in the CSV |
| 2 | **run_calls.py** → **Twilio API** | "Please call +30…" |
| 3 | **Twilio** | Rings the phone; when answered, POSTs to `/voice/inbound` |
| 4 | **FastAPI** `/voice/inbound` | Looks up contact, returns TwiML: `<Connect><Stream url="wss://…/media-stream">` with contact name + language as parameters |
| 5 | **Twilio** | Opens a WebSocket to `/media-stream`; sends inbound audio as base64 μ-law 8 kHz frames |
| 6 | **FastAPI** `/media-stream` | Connects to ElevenLabs Conversational AI WebSocket, passes audio in both directions |
| 7 | **ElevenLabs agent** | Streams STT + LLM + TTS in real time, supports barge-in |
| 8 | Audio flows both ways until end | Person hangs up, or agent ends the session |

While calls are live, you can peek at session state: open `http://127.0.0.1:8001/debug/sessions` (use your `APP_PORT` if different).

---

## First-time setup

Run this once.

```bash
cd caller_app
make setup
cp .env.example .env
cp data/contacts.csv.example data/contacts.csv
```

`data/contacts.csv` is gitignored (it holds real phone numbers). Edit your local copy after copying from the example.

Then edit `.env` and fill in real values:

- **Twilio** — account SID, API key SID (`SK…`), API key secret, and the phone number calls come *from*
- **ElevenLabs** — API key **and the agent ID** (see below)
- **`PUBLIC_BASE_URL`** — leave as placeholder for now; you set it after starting ngrok

### Create the ElevenLabs Conversational AI agent (one-time)

1. Go to [ElevenLabs → Conversational AI → Agents](https://elevenlabs.io/app/conversational-ai/agents) and create an agent (or reuse an existing one).
2. In the agent **Voice** settings, set audio formats for telephony:
   - **Input:** PCM 16000 Hz *(the app transcodes from Twilio μ-law 8 kHz)*
   - **Output:** PCM 16000 Hz
3. Under **Security**, turn **Enable authentication** **On**.
4. Copy agent ID(s) into `.env` as `ELEVENLABS_AGENT_IDS=…` (comma-separated). `ELEVENLABS_AGENT_ID` is optional fallback when the list is empty.

The app **pushes persona, LLM, and first message from this repo** to **every agent in the pool** on startup (`ELEVENLABS_SYNC_AGENT_ON_STARTUP=true`). Each call via `run_calls.py` picks a **random** agent from that list for voice variety:

| Agent | Gender | Voice |
|-------|--------|-------|
| Μαρίνα | female | Marina_Kabardina (clone) |
| Ελένη | female | Matilda |
| Γιώργος | male | George |
| Νίκος | male | Daniel |
| Δημήτρης | male | alex_papadakis (clone) |

Per-agent voice and male/female prompt mapping lives in `app/agent_profiles.py`. Edit:

- `prompts/worried_citizen_system.txt` — female worried-citizen persona
- `prompts/worried_citizen_system_male.txt` — male worried-citizen persona
- `prompts/worried_citizen_first_message.txt` — opening line
- `.env` → `ELEVENLABS_AGENT_LLM` (default `gemini-2.5-flash`)
- `.env` → `REPORT_LOCATION`, `REPORT_PLATE`, `REPORT_CAR_COLOR`, `REPORT_CAR_BRAND`

Then restart the API server, or run:

```bash
make sync-agent
```

Add these **dynamic variables** in the ElevenLabs agent dashboard (Agent → Dynamic variables) so the prompt templates resolve:

`contact_name`, `language`, `notes`, `report_location`, `report_plate`, `report_car_color`, `report_car_brand`

Per-call values come from the CSV contact row (`language`, `notes`) plus the `REPORT_*` fields in `.env`.

**Advanced:** set `ELEVENLABS_USE_RUNTIME_OVERRIDES=true` only if you also enable matching override fields under Security → Overrides in the dashboard. Default is `false` — sync-on-startup is simpler.

### Twilio credentials

The app supports **API Key** auth (recommended) or classic **Account Auth Token** auth.

**API Key (recommended)** — same style as the Twilio MCP server (`AC…/SK…:secret`):

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_api_key_secret
```

Create keys in [Twilio Console → API Keys](https://console.twilio.com/us1/account/keys-credentials/api-keys). When `TWILIO_API_KEY_SID` is set, `TWILIO_AUTH_TOKEN` is the **API key secret**, not the main account Auth Token.

**Account Auth Token (alternative)** — omit `TWILIO_API_KEY_SID` and put the Auth Token from [Account Info](https://console.twilio.com/) in `TWILIO_AUTH_TOKEN`.

Phone numbers in the CSV must use **E.164** format: country code + number, with a `+` at the start.

- Good: `+306972813080`
- Bad: `00306972813080` or `6972813080`

### Choosing which number to call

**Recommended:** pass the contact `name` from the CSV:

```bash
python run_calls.py --contact Marina
```

Or set a default in `.env`:

```env
CALL_CONTACT=Marina
```

Then `python run_calls.py` uses that name. One of `--contact` or `CALL_CONTACT` is required.

Example `data/contacts.csv`:

```csv
name,phone,language,timezone,last_called_at,notes
Me,+306972813080,el,Europe/Athens,,
Marina,+306946424153,el,Europe/Athens,,
```

---

## How to run it

You need **three terminal windows** open at the same time.

### Terminal 1 — start the API server

```bash
cd caller_app
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Or `make run`. Leave it running. You should see `Uvicorn running on http://0.0.0.0:8001`. Do not use `--reload` during live calls; transcript writes under `call_logs/` can trigger reloads and interrupt the media stream.

**Port 8000 already in use?** ComfyUI and other tools often bind `127.0.0.1:8000`. If `curl http://127.0.0.1:8000/health` does **not** return `{"status":"ok"}`, use **8001** for caller_app and ngrok instead.

Quick check: `curl http://127.0.0.1:8001/health` → `{"status":"ok"}`.

### Terminal 2 — start ngrok (public tunnel)

```bash
ngrok http 127.0.0.1:8001
```

Use the **same port** as Terminal 1 and set `APP_PORT=8001` in `.env`. Use `127.0.0.1`, not `localhost`.

Copy the full `https://….ngrok-free.app` URL from ngrok's output (include the domain suffix — a truncated URL will fail).

1. Paste it into `.env` as `PUBLIC_BASE_URL=...` (no trailing slash, full `….ngrok-free.app` domain — a truncated or duplicated URL will make Twilio say "application error"). The app derives the `wss://…/media-stream` URL automatically from this.
2. **Stop and restart Terminal 1** so the app picks up the new URL.

Leave ngrok running.

### Terminal 3 — place the calls

```bash
cd caller_app
source .venv/bin/activate
python run_calls.py --contact Marina
```

`run_calls.py` checks local `/health` and `PUBLIC_BASE_URL/health` **before dialing**. If either fails, it prints what to fix instead of placing a call.

Uses the `REPORT_*` defaults from `.env` for location, plate, color, and brand. **All four fields are required** — if any is missing or blank, `run_calls.py` exits without dialing.

#### Reporting a car with specific details

Override any report field **for this run only** with CLI flags. Omitted flags fall back to `.env`.

**Default report in `.env` (used when you run `python run_calls.py` with no flags):**

```env
REPORT_LOCATION=Μήτρου Σαρκουδινού 7, Νέος Κόσμος, Αθήνα
REPORT_PLATE=ΙΗΧ9037
REPORT_CAR_COLOR=Γκρίζο
REPORT_CAR_BRAND=Ford Mustang
```

**Same details passed explicitly on the CLI:**

```bash
python run_calls.py --contact Marina \
  --location "Μήτρου Σαρκουδινού 7, Νέος Κόσμος, Αθήνα" \
  --plate "ΙΗΧ9037" \
  --color "Γκρίζο" \
  --brand "Ford Mustang"
```

**Different car — blue BMW on a side street:**

```bash
python run_calls.py \
  --location "Οδός Πατησίων 120, Αθήνα" \
  --plate "ΧΝΚ4521" \
  --color "μπλε" \
  --brand "BMW"
```

**Only change plate and location** (color and brand from `.env`):

```bash
python run_calls.py \
  --location "Λεωφόρος Συγγρού, στάση τραμ" \
  --plate "ΑΟΥ1188"
```

**English location, Greek plate** (plate must still use Greek capitals Α–Ω):

```bash
python run_calls.py \
  --location "Syntagma Square, outside the metro exit" \
  --plate "ΕΤΖ7742" \
  --color "white" \
  --brand "Toyota Yaris"
```

Before dialing, the script prints the resolved report details and which random agent was picked. The same values are logged in `call_logs/call_<CallSid>.log` under `report_*` and `agent_id=`.

Or `make call` (uses `CALL_CONTACT` from `.env` when set).

The script calls **one number**. If the contact cannot be resolved, it exits with an error.

You'll see dialing details on separate lines (`Dialing …`, `SID: CA…`, `agent: … (Μαρίνα)`), then live status in the same terminal:

```
Waiting for call to finish...
Ringing Marina...
Marina answered
Call status: completed
```

If nobody picks up within **4 rings** (default `CALL_MAX_RINGS=4` × `CALL_RING_SECONDS=5` → 20s Twilio answer timeout), the call is canceled and you see a no-answer message. **Ctrl+C** during the call cancels ringing or hangs up if already connected.

While calls are live, Terminal 1 (API server) also logs every exchange:

```
[User]  Hi, thank you so much!
[Agent] So glad to hear that! Got any fun plans today?
[Latency] 312ms
```

After each call, a transcript is saved under `call_logs/` as `call_<CallSid>.log` (e.g. `call_CAf471da1b14422a4f9d7da9ead82479dd.log`). Each file includes contact metadata, timestamped Agent/User lines, latency notes, and a **cost summary** table at the end.

### Call cost summary

When a call ends, the API server prints a short table:

```
Call cost summary (CA…)
Service    | This call              | Balance remaining
-----------+------------------------+----------------------------
Twilio     | $0.0120 USD, 45s       | $5.6856 USD
ElevenLabs | 873 credits · 73s      | 12,127 credits (free plan)
```

- **Twilio** — per-call price and duration from the Call resource; account balance from the Balance API.
- **ElevenLabs** — credits used for the agent session (from conversation metadata); remaining credits from your subscription.

`run_calls.py` waits for the call to finish in the same terminal, then prints the cost table (if the API server is running on `APP_PORT`).

For **ElevenLabs balance remaining**, enable the **`user_read`** permission on your API key in the ElevenLabs dashboard. Without it, the call cost still appears but balance shows `n/a`.

---

## How to stop everything

| What to stop | How | Which terminal |
|--------------|-----|----------------|
| API server | Press **Ctrl+C** | Terminal 1 (uvicorn) |
| ngrok tunnel | Press **Ctrl+C** | Terminal 2 |
| `run_calls.py` | Waits for call to finish and prints cost summary; **Ctrl+C** hangs up and exits | Terminal 3 |
| Live call | The agent will end it, or the caller hangs up | — |

To fully deactivate the Python venv in a terminal: `deactivate`.

---

## What costs money

Running the code on your laptop is free. These **cloud services charge you**:

### Twilio (phone calls + media streams)

| Item | Typical cost model |
|------|-------------------|
| **Phone number** | Monthly fee to keep a number |
| **Outbound calls** | Per-minute; **international calls cost more** than domestic |
| **Media Streams** | A small per-minute fee on top of the call minutes |

Every test call to a real mobile number uses real money. **Only call numbers you are allowed to test.** Check pricing in the [Twilio console](https://console.twilio.com/).

> Note: with the new architecture, Twilio no longer does STT (`<Gather>`) — the agent handles it. You don't pay the Twilio speech-recognition line item anymore.

### ElevenLabs (Conversational AI)

| Item | Typical cost model |
|------|-------------------|
| **Conversational AI** | Billed by **minutes of conversation** (not characters) |
| **LLM cost** | Included for built-in models; bring-your-own-key options also exist |
| **Free tier** | Limited minutes per month |

Check usage at [elevenlabs.io](https://elevenlabs.io/app/usage).

### ngrok (tunnel)

| Item | Typical cost model |
|------|-------------------|
| **Free plan** | Random URL each time you start ngrok |
| **Paid plan** | Fixed domain, more stable for production |

The free URL changes every restart — that is why you update `PUBLIC_BASE_URL` and restart uvicorn.

---

## Useful commands (Makefile)

| Command | What it does |
|---------|--------------|
| `make setup` | Create `.venv` and install packages |
| `make run` | Start the API server |
| `make call` | Run `run_calls.py` |
| `make sync-agent` | Push prompt/LLM from `.env` + `prompts/` to ElevenLabs |
| `make health` | Ping `/health` (server must already be running) |

---

## CSV columns (contacts file)

Header row:

`name,phone,language,timezone,last_called_at,notes`

- **name** — used with `--contact` / `CALL_CONTACT` (case-insensitive match)
- **phone** — E.164 number Twilio dials (`+30…`)
- **language** — `el` (Greek) or `en` (English); passed to the agent as a dynamic variable
- **notes** — free text; passed to the agent so it can personalize

---

## Environment variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `PUBLIC_BASE_URL` | Full ngrok `https://….ngrok-free.app` URL (no trailing slash). App derives `wss://…/media-stream` from this. |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (`AC…`) |
| `TWILIO_API_KEY_SID` | Twilio API key SID (`SK…`); omit for auth-token mode |
| `TWILIO_AUTH_TOKEN` | API key secret **or** account Auth Token (see setup above) |
| `TWILIO_FROM_NUMBER` | Outbound caller ID in E.164 (`+1…`, `+30…`, etc.) |
| `ELEVENLABS_API_KEY` | ElevenLabs API key (used to sign the agent WebSocket URL) |
| `ELEVENLABS_AGENT_ID` | *(optional)* Single agent fallback if `ELEVENLABS_AGENT_IDS` is empty |
| `ELEVENLABS_AGENT_IDS` | Comma-separated agent IDs; one chosen at random per outbound call |
| `ELEVENLABS_AGENT_LLM` | LLM model slug (default `gemini-2.5-flash`) |
| `ELEVENLABS_AGENT_LANGUAGE` | Default agent language (default `el`) |
| `ELEVENLABS_AGENT_PROMPT_PATH` | System prompt file (default `prompts/worried_citizen_system.txt`) |
| `ELEVENLABS_AGENT_FIRST_MESSAGE_PATH` | First message file |
| `ELEVENLABS_SYNC_AGENT_ON_STARTUP` | `true` = push prompt/LLM to ElevenLabs when API starts |
| `ELEVENLABS_USE_RUNTIME_OVERRIDES` | `true` = per-call overrides (requires dashboard Overrides enabled) |
| `REPORT_LOCATION` / `REPORT_PLATE` / `REPORT_CAR_COLOR` / `REPORT_CAR_BRAND` | Parking report details for the persona (`REPORT_PLATE` uses Greek capitals, e.g. `ΙΗΧ9037`) |
| `ELEVENLABS_VOICE_ID_EL` | *(optional)* Voice override when using runtime overrides |
| `ELEVENLABS_VOICE_ID_EN` | *(optional)* Voice override when using runtime overrides |
| `CSV_PATH` | Path to contacts file (default `data/contacts.csv`) |
| `CALL_CONTACT` | Default contact `name` when `run_calls.py` is run without `--contact` |
| `CALL_LOGS_DIR` | Directory for per-call transcript logs (default `call_logs`) |
| `CALL_MAX_RINGS` | Max rings before hang-up if unanswered (default `4`) |
| `CALL_RING_SECONDS` | Seconds per ring for answer timeout (default `5`; Twilio timeout = rings × this) |
| `TIMEZONE` | Default timezone stored on contacts when CSV row omits it |

See `.env.example` for the full list.

---

## Rules while working on this

1. **Never commit `.env`** — it has secret keys.
2. **Only call test numbers you own or have permission to use.**
3. **Twilio `TWILIO_FROM_NUMBER` must be a number you control in Twilio** — no fake caller ID.
4. If something fails, check:
   - Is uvicorn running on the port ngrok forwards to?
   - Is ngrok running, and does `PUBLIC_BASE_URL` match its **full** current URL?
   - Is `ELEVENLABS_AGENT_IDS` (or `ELEVENLABS_AGENT_ID`) set? The app transcodes between Twilio μ-law 8 kHz and the agent's PCM 16 kHz audio. If you manually change agent audio formats, update `app/twilio_audio_interface.py` too.
   - Are Twilio credentials API-key style (`TWILIO_API_KEY_SID` + secret) or auth-token style — not mixed up?
5. After renaming or moving this project folder, run `make clean && make setup` to rebuild `.venv` (venv paths are absolute).

---

## Where to look in the code

| If you want to change… | Open… |
|------------------------|-------|
| Random agent pool per call | `app/agent_context.py`, `app/agent_profiles.py`, `ELEVENLABS_AGENT_IDS` in `.env` |
| Agent persona, LLM, parking report details | `prompts/worried_citizen_*.txt`, `.env`, `app/agent_config.py` |
| Push agent config to ElevenLabs | `sync_agent.py`, `make sync-agent` |
| Call transcripts / costs | `call_logs/call_<CallSid>.log`, `app/call_log.py`, `app/call_costs.py` |
| Webhook + WebSocket flow | `app/main.py` |
| Audio bridging (Twilio ↔ ElevenLabs) | `app/twilio_audio_interface.py` |
| How calls are started / canceled | `run_calls.py`, `app/twilio_client.py` |
| Contact / call schedule logic | `app/csv_store.py` |
| Settings and env vars | `app/config.py`, `.env.example` |

Good first tasks: tweak the agent's system prompt in the dashboard, add a new language column, or wire `notes` into a richer personalization prompt.
