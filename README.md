# Zolabs Voice Form Tester

Internal **test tool** for checking how well OpenAI speech-to-speech models run a
form-filling phone-style survey. It asks questions one by one, handles follow-ups,
and saves answers as structured data through tool calls.

> **TEST MODE - use dummy data only.** No real names, phone numbers, Aadhaar or
> beneficiary data. This is not a production system.

Models under test:
- **GPT-Live 1** (`gpt-live-1`): the primary model.
- **gpt-realtime-2.1**: for comparison.

---

## Setup

You need Python 3.11+, Node 18+, Chrome or Edge, and a headset (strongly recommended).

```bash
# 1. Secrets
cp .env.example .env          # then put your key in OPENAI_API_KEY

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt   # also installs ../report_module
playwright install chromium       # once, for PDF reports (~150 MB)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                    # opens on http://localhost:5173
```

On startup the backend creates `backend/data/app.db` (SQLite) and loads every
form JSON file in `backend/seed_forms/`. It also adds any new columns to an
existing `app.db` automatically, so calls made earlier are kept.

## Running a test call

1. Open http://localhost:5173 and allow microphone access.
2. Column 1: pick the form, model, language, voice and **audio mode** (Normal or
   Phone 8 kHz). "Record agent voice" saves only the agent's audio, for the optional
   MOS score. Use it on dummy calls only.
3. Click **Start Call**.
   - **GPT-Live:** say "hello" first. The agent then greets you.
   - **gpt-realtime-2.1:** the agent speaks first.
4. Answer using made-up data. Try the edge cases:
   - an age outside 18-100
   - "no" to attended sessions (the reason follow-up should appear)
   - 2 children but only one age
   - correcting an earlier answer
   - interrupting the agent
5. Watch Column 2 (form cards) and Column 3 (metrics) update live.
6. Click **End Call**. Mark each filled field **Correct** or **Wrong**, and type the expected value where needed.
7. **Export JSON** or **Export CSV** to download the raw call data.
8. When the call ends, a **post-call report** is generated automatically. Click
   **Report ready - open post-call report** to view it in a new tab. On the report page:
   - add the 1-5 voice ratings
   - click **Regenerate report** after changing Correct/Wrong marks
   - download the PDF, Markdown or JSON
   - optionally generate an AI summary

   See [report_module/README.md](report_module/README.md).

**Simulate** replays [frontend/src/simulate/sampleReplay.json](frontend/src/simulate/sampleReplay.json)
through the real backend. It uses no microphone, no OpenAI and costs nothing. It works
without an API key and is the quickest way to check the UI. The script includes one
invalid age and one wrong children count, so you can see rejections.

## Running tests

```bash
cd backend
.venv\Scripts\activate
pytest -q                          # tester + report integration
pytest -q ../report_module/tests   # report metrics, exports, PII masking
```

The tester tests cover field validation, follow-up conditions, the `complete_form`
missing-field check, scoring, export and the end-to-end report flow. The report-module
tests cover WER/CER (English, Hindi, Tamil), correction detection, number mishearings,
latency stats, accuracy, cost, the overall score, PII masking and the JSON schema. All
tests use in-memory data and need no API key.

To point the frontend at a backend on another port, set `API_TARGET` for Vite, for
example `API_TARGET=http://127.0.0.1:8001 npx vite --port 5174`.

---

## How it works

```
Browser (React)                 Backend (FastAPI)                OpenAI
  mic + SDP offer  ───────────▶ POST /api/session ─────────────▶ /v1/live/sessions  (GPT-Live)
                                  (API key added here)           /v1/realtime/calls (gpt-realtime)
  SDP answer       ◀─────────── returns SDP answer only ◀───────
  audio  ◀═════════════════════ WebRTC media + "oai-events" data channel ═════════════▶
  tool call event  ───────────▶ POST /api/tools/{name}  (validate + save in SQLite)
  function output  ─────────────────────────────── data channel ──────────────────────▶
```

- **The API key stays on the server.** The browser sends only its WebRTC offer. The
  backend calls OpenAI with the key and returns only the SDP answer and session id.
  There is no key or token in frontend code, logs or git (`.env` is git-ignored).
- **The backend owns all form rules.** Type, range and choice checks, follow-up
  conditions and the required-field check all live in
  [backend/app/services/form_logic.py](backend/app/services/form_logic.py).
  When a value is invalid, the tool returns `ok: false` with a message, and the agent re-asks.
- **Instructions come from the selected form.**
  [backend/app/services/prompt.py](backend/app/services/prompt.py) builds them from
  the form JSON and the chosen language. Nothing about the survey is hard-coded.

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | Dropdown options, cost rates, whether a key is configured (never the key itself) |
| GET | `/api/forms` | List forms |
| GET | `/api/forms/{id}` | Form definition |
| POST | `/api/calls` | Create a call record (also used by Simulate) |
| POST | `/api/session` | Exchange the browser's SDP offer for OpenAI's SDP answer |
| POST | `/api/tools/{tool_name}` | Run a tool call: validate and save |
| POST | `/api/calls/{id}/turns` | Save one response-time measurement |
| POST | `/api/calls/{id}/end` | Save duration, interruptions, usage and transcript |
| GET | `/api/calls/{id}` | Answers, scores, metrics, tool calls and transcript |
| POST | `/api/calls/{id}/review` | Save a tester's Correct/Wrong mark |
| GET | `/api/calls/{id}/export?format=json\|csv` | Download the report |

Tables: `forms`, `calls`, `answers`, `tool_calls`, `turn_metrics`, `reviews`. The
transcript is stored as JSON on `calls`.

### Adding a form

Copy [backend/seed_forms/program_feedback_survey.json](backend/seed_forms/program_feedback_survey.json),
change it, and restart the backend.

Field types:
- `text`
- `number` (with `integer`, `min`, `max`)
- `choice` (with `choices`)
- `yes_no`
- `list_number` (with `min`, `max`, `count_field`)

A follow-up field has a condition, for example
`"condition": {"field": "number_of_children", "op": "gt", "value": 0}`.
Supported operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`.

### Metrics

- **Response time per turn:** the time from the caller going quiet to the first agent
  audio. It is measured in the browser from audio levels ([frontend/src/voice/audioMeter.js](frontend/src/voice/audioMeter.js)).
  It includes network and playback delay, so it is what a caller actually hears.
- **Interruptions (barge-ins):** the caller starts speaking while agent audio is playing.
  Use a headset; speaker echo can count as a false barge-in.
- **Accuracy** = fields marked Correct ÷ filled fields. Unreviewed fields count as not correct, so review every field.
- **Completion** = filled required fields ÷ required fields. Only follow-ups whose condition is met are counted.
- **Cost** uses the billed seconds OpenAI reports (`session.usage.updated`) when they are available. Otherwise it uses call duration × the configured rate.

---

## Where the docs differ from the original brief

These were checked against developers.openai.com in October 2026.

1. **No ephemeral token for GPT-Live.** The GPT-Live WebRTC guide uses only a
   server-side flow: the backend posts the browser's SDP offer to `POST /v1/live/sessions`
   with the project key. So `/api/session` returns the SDP answer, not a token. For a
   consistent comparison, gpt-realtime-2.1 also uses its server-side flow (`POST /v1/realtime/calls`).
   The security goal is still met, because the key never reaches the browser.
2. **GPT-Live calls tools through delegation.** The voice model hands the work to a
   Responses "backend" model, set by `LIVE_DELEGATE_MODEL` (default `gpt-5.6-terra`), and our
   four tools are registered on it as `delegation.responses.tools`. The browser reads the
   call from `response.event` → `response.output_item.done`, then sends back
   `response.item.create` (`function_call_output`) and `response.create`.
   **The delegated model's tokens are billed separately** from the $0.05/min voice price
   and are not in the cost estimate.
3. **`save_answer.value` is a string, not "any".** Strict JSON schema needs every
   property typed. The agent sends `"34"`, `"yes"` or `"4, 7"`, and the backend converts it.
4. **No speech start/stop events in GPT-Live.** GPT-Live does not document them, so
   response time is measured from audio levels for both models (see Metrics).
5. **`strict` is not sent for gpt-realtime-2.1.** The Realtime function-calling guide
   does not document it. GPT-Live's delegated Responses tools do use `strict: true`.
6. **Voices and languages.** GPT-Live and Realtime list different voices, so the
   dropdown changes with the model. The GPT-Live docs do not list supported languages,
   so the language is set through the instructions. Check quality per language during testing.
7. **GPT-Live start.** No documented event makes GPT-Live speak first over WebRTC, so
   the caller says "hello" to begin. gpt-realtime-2.1 is started with `response.create`.

### Not yet verified against a live API

These parts follow the docs but have not been run with a real key yet. Check them on the first call:
- GPT-Live session fields `audio.output.voice` and `delegation.responses.parallel_tool_calls`.
  The delegation guide shows `delegation.responses.{model, instructions, tools, tool_choice}`.
- Whether `session.input_transcript.delta` arrives without extra transcription settings.
- The Realtime multipart `session` field and the `Location` header for the call id.

If OpenAI rejects a field, the error appears in red in Column 3, and the backend returns the OpenAI message.

### Docs relied on

- [GPT-Live: Getting started](https://developers.openai.com/api/docs/guides/live): delegation modes and the application's role.
- [WebRTC](https://developers.openai.com/api/docs/guides/realtime-webrtc) / [Voice WebRTC (Live)](https://developers.openai.com/api/docs/guides/voice-webrtc?api=live): server-side SDP exchange, `oai-events` channel, omit `audio.format`, 201 response shape.
- [Managing GPT-Live sessions](https://developers.openai.com/api/docs/guides/live-conversations): `session.started`, transcript deltas, `session.usage.updated`, `session.close` / `session.closed`, mute events, errors.
- [Delegation and tools](https://developers.openai.com/api/docs/guides/live-delegation): `response.event` envelope, `function_call_output` + `response.create`.
- [Prompting GPT-Live](https://developers.openai.com/api/docs/guides/live-prompting): template headings, `<|SpawnThinking|>`.
- [GPT-Live 1 model page](https://developers.openai.com/api/docs/models/gpt-live-1): $0.05/min billed per second, 15-second WebRTC init charge.
- [Realtime function calling](https://developers.openai.com/api/docs/guides/realtime-function-calling): `session.tools`, `response.done` function calls, `conversation.item.create`.
- [Function calling (strict mode)](https://developers.openai.com/api/docs/guides/function-calling): `additionalProperties: false`, all properties required.

## Policy reminders (EdZola)

- Dummy data only. Never paste real beneficiary data into the app or into transcripts.
- Use only the key in `.env`. Never commit it or paste it into chats.
- AI-assisted code: tag it in PR descriptions and get a human review before merging.
