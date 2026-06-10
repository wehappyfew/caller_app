# caller_app

A small Python app that **calls people on their birthday**, plays a spoken greeting, listens to what they say, replies once, and hangs up.

This README is written so you can set it up, run it, and understand what each piece does.

---

## What the app does (big picture)

1. You keep a list of people in a spreadsheet file (`data/contacts.csv`).
2. When you run the caller script, it checks **who has a birthday today**.
3. For each match, it asks **Twilio** (a phone company API) to ring that person.
4. When they pick up, **Twilio** talks to **your Python server** over the internet.
5. Your server creates a birthday message, turns it into audio with **ElevenLabs** (AI voice), and tells Twilio to play it.
6. Twilio records what the person says, sends the text back to your server, your server replies with more audio, then the call ends.

You trigger calls manually — nothing runs on a schedule yet.

---

## The parts (what each thing is for)

| Part | What it is | What it does in this app |
|------|------------|--------------------------|
| **`data/contacts.csv`** | A simple contact list | Names, phone numbers, birthdays, language (`el` or `en`) |
| **`run_calls.py`** | A short Python script you run by hand | Finds today's birthdays and tells Twilio to start calling |
| **`app/main.py`** | The web server (FastAPI) | Receives webhooks from Twilio during a live call |
| **`app/conversation.py`** | The "brain" text | Writes what the bot says (Greek or English) |
| **`app/elevenlabs_tts.py`** | Text-to-speech helper | Sends text to ElevenLabs, saves an `.mp3` file |
| **`app/csv_store.py`** | CSV reader | Loads contacts and checks birthdays |
| **`.env`** | Secret config file (not in git) | API keys, phone number, public URL |
| **Twilio** | Cloud phone service | Makes real phone calls, speech-to-text, plays audio |
| **ElevenLabs** | Cloud voice AI | Turns written text into natural-sounding speech |
| **ngrok** | Tunnel tool | Gives your laptop a public URL so Twilio can reach your local server |
| **uvicorn** | Web server runner | Keeps `app/main.py` listening on port 8000 |

Think of it like this:

```
You → run_calls.py → Twilio → person's phone
                         ↕ (during the call)
                    ngrok → your FastAPI app → ElevenLabs
```

---

## What happens during one call (step by step)

| Step | Who does it | What happens |
|------|-------------|--------------|
| 1 | **You** run `python run_calls.py` | Script reads CSV, finds birthdays today |
| 2 | **run_calls.py** → **Twilio API** | "Please call +30…" |
| 3 | **Twilio** | Rings the phone; when answered, opens a call session |
| 4 | **Twilio** → **ngrok** → **FastAPI** (`/voice/inbound`) | "They picked up — what should I do?" |
| 5 | **FastAPI** | Looks up contact, builds greeting text, calls **ElevenLabs** for audio |
| 6 | **FastAPI** → **Twilio** | Returns TwiML (XML instructions): "play this MP3, then listen" |
| 7 | **Twilio** | Plays audio to the person, converts their speech to text |
| 8 | **Twilio** → **FastAPI** (`/voice/process`) | Sends what the person said |
| 9 | **FastAPI** | Picks a reply, generates more audio via **ElevenLabs**, tells Twilio to play it and hang up |
| 10 | **Twilio** | Ends the call |

While a call is live you can peek at state: open `http://127.0.0.1:8000/debug/sessions` in a browser.

---

## First-time setup

You only do this once (or after pulling big dependency changes).

```bash
cd caller_app
make setup
cp .env.example .env
```

Then edit `.env` and fill in real values (ask whoever gave you this repo for the keys):

- **Twilio** — account SID, auth token, and the phone number calls come *from*
- **ElevenLabs** — API key and voice IDs for Greek and English
- **`PUBLIC_BASE_URL`** — leave as placeholder for now; you set it after starting ngrok

Phone numbers in the CSV must use **E.164** format: country code + number, with a `+` at the start.

- Good: `+306972813080`
- Bad: `00306972813080` or `6972813080`

To test a specific number, add a row in `data/contacts.csv` with today's month/day as the birthday (year does not matter).

---

## How to run it

You need **three terminal windows** open at the same time.

### Terminal 1 — start the API server

**Runs:** `uvicorn` + your FastAPI app on your laptop (port 8000)

```bash
cd caller_app
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Leave this running. You should see `Uvicorn running on http://0.0.0.0:8000`.

Quick check (optional, in another terminal): `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`

### Terminal 2 — start ngrok (public tunnel)

**Runs:** `ngrok` — forwards internet traffic to your local port 8000

```bash
ngrok http 127.0.0.1:8000
```

Use `127.0.0.1`, not just `localhost` — on some Macs `localhost` breaks the tunnel.

Copy the `https://….ngrok-free.app` URL from ngrok's output.

1. Paste it into `.env` as `PUBLIC_BASE_URL=...` (no trailing slash).
2. **Stop and restart Terminal 1** (Ctrl+C, then run uvicorn again) so the app picks up the new URL. Audio file links depend on this.

Leave ngrok running too.

### Terminal 3 — place the calls

**Runs:** `run_calls.py` once — talks to Twilio, then exits

```bash
cd caller_app
source .venv/bin/activate
python run_calls.py
```

It only calls people who:

- have a birthday **today** (timezone `Europe/Athens` by default),
- have `opt_in` = true,
- have `opt_out` = false.

You'll see lines like `Queued call for … - SID: CA…`.

---

## How to stop everything

| What to stop | How | Which terminal |
|--------------|-----|----------------|
| API server | Press **Ctrl+C** | Terminal 1 (uvicorn) |
| ngrok tunnel | Press **Ctrl+C** | Terminal 2 |
| `run_calls.py` | Finishes on its own; or **Ctrl+C** if stuck | Terminal 3 |

Order does not matter much, but stop uvicorn and ngrok when you are done testing so nothing is listening on your machine.

To fully deactivate the Python venv in a terminal: `deactivate`

---

## What costs money

Running the code on your laptop is free. These **cloud services charge you**:

### Twilio (phone calls)

| Item | Typical cost model |
|------|-------------------|
| **Phone number** | Monthly fee to keep a number (e.g. a US number) |
| **Outbound calls** | Per-minute charge; **international calls cost more** than domestic |
| **Speech recognition** | Twilio bills for the speech-to-text used during `Gather` |

Every test call to a real mobile number uses real money. **Only call numbers you are allowed to test** (your own phone, with permission).

Check your balance and pricing in the [Twilio console](https://console.twilio.com/).

### ElevenLabs (AI voice)

| Item | Typical cost model |
|------|-------------------|
| **API usage** | Billed by **characters** converted to speech |
| **Free tier** | Limited characters per month; then paid plans |

Each greeting + reply in a call = at least two TTS requests. Longer messages = more characters.

Check usage at [elevenlabs.io](https://elevenlabs.io/).

### ngrok (tunnel)

| Item | Typical cost model |
|------|-------------------|
| **Free plan** | Random URL each time you start ngrok; fine for learning |
| **Paid plan** | Fixed domain, more stable for production |

The free URL changes every restart — that is why you update `PUBLIC_BASE_URL` and restart uvicorn.

### Free / local

- Python, FastAPI, uvicorn, the CSV file, and code in this repo — **no charge**
- Your home internet — normal usage

---

## Useful commands (Makefile)

| Command | What it does |
|---------|--------------|
| `make setup` | Create `.venv` and install packages |
| `make run` | Start the API server |
| `make call` | Run `run_calls.py` |
| `make health` | Ping `/health` (server must already be running) |

---

## CSV columns (contacts file)

Header row:

`name,phone,birthday,language,timezone,opt_in,opt_out,last_called_at,notes`

- **birthday** — `YYYY-MM-DD` (only month + day are used for "today")
- **language** — `el` (Greek) or `en` (English)
- **opt_in / opt_out** — must be `true`/`false`; only opted-in, not opted-out contacts get called

---

## Rules while working on this

1. **Never commit `.env`** — it has secret keys.
2. **Only call test numbers you own or have permission to use.**
3. **Twilio `TWILIO_FROM_NUMBER` must be a number you control in Twilio** — no fake caller ID.
4. If something fails, check: Is uvicorn running? Is ngrok running? Does `PUBLIC_BASE_URL` match ngrok's current URL?

---

## Where to look in the code

| If you want to change… | Open… |
|------------------------|-------|
| What the bot says | `app/conversation.py` |
| How calls are started | `run_calls.py` |
| Webhook / call flow logic | `app/main.py` |
| Voice / TTS | `app/elevenlabs_tts.py` |
| Contact / birthday logic | `app/csv_store.py` |
| Settings and env vars | `app/config.py`, `.env.example` |

Good first tasks: tweak the birthday messages, add a new language, or improve how the CSV is read.
