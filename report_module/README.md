# Post-Call Report module (`report_module`)

This shared Python module turns one test call into a report with 10 sections.

The report looks the same for all four Zolabs voice testers (OpenAI, Sarvam, Gemini and
ElevenLabs), so reports from different providers can be compared side by side.

> **TEST MODE - dummy data only.** Reports are AI-assisted. A team member must review
> every report before it is shared outside EdZola.

```
tester DB ──adapter──▶ CallData ──build_report()──▶ report dict ──▶ React page / PDF / Markdown / JSON
           (per app)    (one format)  (shared)       (one schema)
```

## Report sections

1. **Summary:** an overall score from 0 to 100, a verdict, and 3 strengths and 3 problems.
2. **Transcript:** colour highlights mark mishearings (red), re-asked questions (orange),
   tool calls (blue), interruptions (purple) and replies in the wrong language (grey).
3. **Mishearings:** word and character error rates (WER and CER, when an expected caller
   script exists), caller corrections, saved values that differ from the expected values,
   and number mix-ups (for example "fifteen" saved as 50, or Hindi "teen" saved as 13).
4. **Voice quality:** tester ratings from 1 to 5, an optional automatic MOS score, long
   silences, talk-overs, cut-off sentences and repeated phrases.
5. **Latency:** average, median, p90 and max reply times, a per-turn chart, the
   STT/LLM/TTS split (Sarvam only) and the 3 slowest turns with what was happening.
6. **Language:** the selected language compared with the detected languages, the share of
   agent turns in the right language, code-mixing, and language-specific mishearings.
7. **Accuracy:** field accuracy, completion, follow-up questions, error recovery and tool
   calls, plus a table of every field.
8. **Cost:** in USD and INR, a breakdown, cost per minute, cost per completed form, and a
   projection for 1,000 calls.
9. **Issues:** sorted by severity, each with a suggested fix.
10. **AI summary (optional):** labelled as AI-generated. Every number in it is checked
    against the computed metrics.

## Install

```bash
# inside the tester's virtualenv
pip install -e "../report_module[pdf,test]"
playwright install chromium        # ~150 MB, once; needed for PDF only
pip install -e "../report_module[mos]"   # OPTIONAL, ~2 GB (PyTorch), for automatic MOS
```

To run the tests: `pytest report_module/tests` (no API key needed).

## Plugging the report into a tester

### 1. Write an adapter

The adapter turns your tester's data into `CallData`. See `call_data.py` for every
field; anything you leave out appears as "n/a" in the report.
[adapters/openai_tester.py](adapters/openai_tester.py) is a complete example to copy.

| CallData field | What to give it |
|---|---|
| `call` | provider (`openai`, `sarvam`, `gemini` or `elevenlabs`), model, voice, language, `audio_mode` (`normal` or `phone_8khz`), `started_at`, `duration_s`, `form_completed` |
| `transcript` | `role` (`caller` or `agent`), `text`, `ts_ms` (ms since the call connected), and optionally `detected_language` |
| `fields` | the form fields with `saved_value`, `expected_value` and `review_mark` (`correct` or `wrong`) |
| `turn_metrics` | `latency_ms` and `ts_ms`. **Sarvam** should also send `stt_ms`, `llm_ms` and `tts_ms` |
| `tool_calls` | `name`, `arguments`, `success`, `result`, `duration_ms` and `ts_ms` |
| `usage` | whatever the provider reports: `voice_seconds`, `audio_in_tokens`, `llm_input_tokens`, `tts_characters`, … |
| `events` | `{"type": "barge_in", "ts_ms": …}` for each interruption |
| `ratings` | tester 1-5 ratings (saved through `POST /ratings`) |
| `scenario` | optional expected caller script and answers (from the comparison tool) |
| `agent_audio_path` | optional WAV of the agent's voice, used for MOS |

### 2. Add the routes

The tester supplies 4 small functions; the module provides the routes.

```python
from report_module.api import make_report_router

router = make_report_router(
    get_call_data=lambda call_id: my_adapter(call_id),   # -> CallData | None
    save_report=lambda call_id, report: ...,             # store JSON in your DB
    load_report=lambda call_id: ...,                     # -> dict | None
    save_ratings=lambda call_id, ratings: ...,           # store tester ratings
)
app.include_router(router)
```

This adds these routes:

| Method | Path | |
|---|---|---|
| POST | `/api/calls/{id}/report?ai_summary=false` | generate or regenerate |
| GET | `/api/calls/{id}/report` | report JSON (generated if missing) |
| POST | `/api/calls/{id}/ratings` | save 1-5 ratings, then regenerate |
| GET | `/api/calls/{id}/report/export?format=pdf\|md\|json` | download as `report_{provider}_{model}_{language}_{date}_{call_id}` |

### 3. Generate automatically

Call `router.generate_report(str(call_id))` when the call ends (End Call) and when
`complete_form` succeeds. Wrap the call in try/except so a report error never breaks
a call. See `generate_report_safely` in
[backend/app/services/report_bridge.py](../backend/app/services/report_bridge.py).

### 4. Add the report page

Copy [frontend/src/components/report/](../frontend/src/components/report/), add
`recharts` to the frontend, and open `/?report=<call_id>` in a new tab (see
`frontend/src/main.jsx`). The page needs only the API routes above.

## Settings ([settings.json](settings.json))

| Key | What it does |
|---|---|
| `score_weights` | Weights for the overall score. Defaults: accuracy 35, mishearings 15, latency 20, voice quality 15, language 10, cost 5. Parts with no data are left out and their weight is shared by the others. |
| `latency_thresholds_ms` | Good below 1000 ms, OK up to 1500 ms, Poor above 1500 ms; a score of 0 at 3000 ms |
| `currency.inr_per_usd` | **Placeholder (88.0). Update it before sharing reports.** |
| `cost.providers` | Rates per provider and model. **Only the GPT-Live price ($0.05/min) has been checked against official pricing.** The others are `null` ("rate not set") and are marked unverified. |
| `cost.rates_last_updated` | Date shown on every report |
| `mos.enabled` | Automatic MOS score (UTMOS22 strong, through `torch.hub` `tarepan/SpeechMOS`). Its code is MIT-licensed. **The model weights' licence is not stated, so use it for internal evaluation only.** |
| `ai_summary.auto_on_generate` | `false` (default) means the AI summary is written only when someone clicks "Generate AI summary". |
| `ai_summary.model` | OpenAI Responses API model. It can be overridden with `SUMMARY_MODEL`; the key comes from `OPENAI_API_KEY`. |

A tester can use its own copy of the settings with `make_report_router(..., settings_path="my_settings.json")`.

## How the scores work

Each part produces a score from 0 to 100:

| Part | Formula |
|---|---|
| Accuracy | 70% field accuracy + 30% completion. If no field was marked Correct or Wrong, completion alone. |
| Mishearings | 100 − 15 per unfixed mishearing − 5 per fixed one, averaged with (1 − CER) when a script exists |
| Latency | 100 at or below 1000 ms, falling in a straight line to 0 at 3000 ms (average reply time) |
| Voice quality | average tester rating (1 → 0, 5 → 100), averaged with MOS if available |
| Language | % of agent turns in the right language; 80/20 with the code-mixing rating if one is given |
| Cost | 100 at or below the target cost per minute, falling to 0 at 3× the target |

Verdicts: **Good** is 75 or above, **Needs improvement** is 50-74, and **Poor** is below 50.
A call with any High-severity issue is never "Good".

## Safety

- **Phone and Aadhaar-style numbers are masked before any section is built**
  (10-digit phone numbers, with or without +91, and 12-digit Aadhaar numbers, in any
  script's digits). Only the last 2 digits are kept, and the report shows a warning.
  **Numbers spoken as words ("nine eight seven…") are not detected.**
- **API keys are read only from the environment** and are never written into reports or logs.
- **Every page, PDF footer and Markdown export** carries "TEST MODE - dummy data only" and
  "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola."
- **The AI summary receives only the computed metrics and the masked transcript.** Any
  number it writes that we did not send is listed in red as "unverified".

## Known limits

- **Without an expected caller script, mishearings nobody corrected can't be detected.**
  WER and CER need the scenario script.
- **Language detection is local and simple.** Indian scripts are detected from their
  Unicode ranges, and romanised Hindi from a word list. **Romanised Tamil, Telugu,
  Kannada, Bengali or Marathi are reported as English.** Hindi and Marathi both use
  Devanagari, so the selected language decides between them.
- **"Long silences" are reply times over 2 s.** The silence inside the agent's audio
  isn't analysed.
- **Older calls** (made before this module was added) have no barge-in times or turn
  times, so their slowest-turn context and interruption highlights are limited.

## JSON schema

[exporters/report.schema.json](exporters/report.schema.json) (version `1.0`) is the
fixed format for the comparison tool. The tests validate all 4 sample reports against
it. Bump `SCHEMA_VERSION` in `report_builder.py` whenever a field is renamed or removed.

## Sample data

The [samples/](samples/) folder has one made-up call per provider. To regenerate them,
run `python samples/make_samples.py`. To build a report without a real call:

```python
from report_module import build_report, CallData
data = CallData.model_validate_json(open("report_module/samples/sarvam.json", encoding="utf-8").read())
report = build_report(data)
```
