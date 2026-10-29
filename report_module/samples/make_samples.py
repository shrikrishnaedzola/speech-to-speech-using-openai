"""Generate the 4 sample CallData files (one per provider). ALL DATA IS MADE UP.

Run:  python -m report_module.samples.make_samples   (or python make_samples.py)
Each sample shows different problems so every report section has something in it:
- openai:     English, "fifteen" heard as 50 then corrected, slow replies after tool calls
- sarvam:     Hindi/Hinglish, STT/LLM/TTS split, Hindi "teen" (3) saved as 13 and never fixed
- gemini:     Tamil, one agent reply in English (wrong language)
- elevenlabs: English, phone 8 kHz mode, fast, contains a fake phone number (gets masked)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

FIELDS = [
    ("caller_name", "Caller name", "text", True, None),
    ("age", "Age", "number", True, None),
    ("district", "District", "text", True, None),
    ("preferred_language", "Preferred language", "choice", False, None),
    ("attended_sessions", "Attended sessions", "yes_no", True, None),
    ("reason_not_attended", "Reason not attended", "text", True, "attended_sessions = no"),
    ("sessions_attended_count", "Sessions attended", "number", True, "attended_sessions = yes"),
    ("number_of_children", "Number of children", "number", True, None),
    ("children_ages", "Children's ages", "list_number", True, "number_of_children > 0"),
    ("satisfaction_rating", "Satisfaction rating", "number", True, None),
    ("improvement_suggestion", "Improvement suggestion", "text", False, None),
    ("consent_to_followup", "Consent to follow-up", "yes_no", True, None),
]


class Call:
    """Tiny helper to write a conversation with automatic timestamps."""

    def __init__(self):
        self.t = 0.0
        self.transcript, self.tools, self.turns, self.events = [], [], [], []
        self._reply_at = None  # when the agent's next reply should start

    def agent(self, text, gap=600):
        # Start at the measured reply time if a caller turn came before.
        self.t = max(self.t + 100, self._reply_at) if self._reply_at else self.t + gap
        self._reply_at = None
        self.transcript.append({"role": "agent", "text": text, "ts_ms": self.t})
        self.t += len(text.split()) * 330  # speaking time

    def caller(self, text, latency=900, gap=700, stt=None, llm=None, tts=None):
        """Caller speaks; the agent's next reply comes after `latency` ms."""
        self.t += gap
        self.transcript.append({"role": "caller", "text": text, "ts_ms": self.t})
        self.t += len(text.split()) * 350
        metric = {"turn": len(self.turns) + 1, "latency_ms": latency, "ts_ms": self.t + latency}
        if stt is not None:
            metric.update(stt_ms=stt, llm_ms=llm, tts_ms=tts)
        self.turns.append(metric)
        self._reply_at = self.t + latency

    def save(self, field_id, value, ok=True, error=None, parsed=None):
        self.t += 150
        result = {"ok": True, "saved": field_id, "value": parsed if parsed is not None else value} if ok \
            else {"ok": False, "error": error}
        self.tools.append({"name": "save_answer", "arguments": {"field_id": field_id, "value": str(value), "confidence": "high"},
                           "success": ok, "result": result, "duration_ms": 11.0, "ts_ms": self.t})

    def tool(self, name, ok=True, result=None, args=None):
        self.t += 150
        self.tools.append({"name": name, "arguments": args or {}, "success": ok, "result": result or {"ok": ok},
                           "duration_ms": 9.0, "ts_ms": self.t})

    def barge_in(self):
        self.events.append({"type": "barge_in", "ts_ms": self.t + 200})


def fields(saved: dict, expected: dict, marks: dict, active_extra=()):
    out = []
    for fid, label, ftype, required, cond in FIELDS:
        active = cond is None or fid in active_extra
        status = "filled" if fid in saved else ("skipped" if fid == "improvement_suggestion" else "pending")
        out.append({
            "id": fid, "label": label, "type": ftype, "required": required, "condition": cond, "active": active,
            "status": status if active else "pending", "saved_value": saved.get(fid),
            "expected_value": expected.get(fid), "review_mark": marks.get(fid),
        })
    return out


def openai_sample():
    c = Call()
    c.caller("Hello", latency=1800)
    c.agent("Hello! I am calling from the program team. This takes about 3 minutes. Is this a good time?")
    c.caller("Yes, go ahead.", latency=1500)
    c.agent("Thank you. May I know your name, please?")
    c.caller("My name is Test Person One.", latency=2600); c.save("caller_name", "Test Person One")
    c.agent("Thank you. How old are you?")
    c.caller("I am thirty five.", latency=2400); c.save("age", "35", parsed=35)
    c.agent("Which district do you live in?")
    c.caller("Sample District.", latency=2200); c.save("district", "Sample District")
    c.agent("Did you attend any of the program sessions?")
    c.caller("Yes I did.", latency=2900); c.save("attended_sessions", "yes", parsed=True)
    c.agent("How many sessions did you attend?")
    # Caller said "fifteen"; the transcript shows what the AI heard.
    c.caller("Fifty sessions.", latency=3100); c.save("sessions_attended_count", "50", parsed=50)
    c.agent("Okay, fifty sessions. How many children do you have?")
    c.barge_in()
    c.caller("No, I said fifteen, not fifty.", latency=2700); c.save("sessions_attended_count", "15", parsed=15)
    c.agent("Sorry about that, fifteen sessions. How many children do you have?")
    c.caller("Two.", latency=2100); c.save("number_of_children", "2", parsed=2)
    c.agent("What are the ages of your children?")
    c.caller("Six.", latency=2500)
    c.save("children_ages", "6", ok=False, error="Got 1 values but number_of_children is 2. Please confirm with the caller.")
    c.agent("You said two children. Could you tell me both ages?")
    c.caller("Six and nine.", latency=2300); c.save("children_ages", "6, 9", parsed=[6, 9])
    c.agent("On a scale of 1 to 5, how satisfied are you with the program?")
    c.caller("Four.", latency=2000); c.save("satisfaction_rating", "4", parsed=4)
    c.agent("Any suggestion to improve the program?")
    c.caller("No, nothing.", latency=1900); c.tool("skip_field", args={"field_id": "improvement_suggestion", "reason": "none"})
    c.agent("May we call you again later for a follow-up?")
    c.caller("Yes, that's fine.", latency=2200); c.save("consent_to_followup", "yes", parsed=True)
    c.agent("To confirm: Test Person One, 35, Sample District, 15 sessions, two children aged 6 and 9, rating 4. Correct?")
    c.caller("Yes, correct.", latency=2400); c.tool("complete_form", result={"ok": True})
    c.agent("Thank you for your time. Have a good day!")

    saved = {"caller_name": "Test Person One", "age": 35, "district": "Sample District", "attended_sessions": True,
             "sessions_attended_count": 15, "number_of_children": 2, "children_ages": [6, 9],
             "satisfaction_rating": 4, "consent_to_followup": True}
    expected = {**saved}
    marks = {k: "correct" for k in saved}
    return {
        "call": {"call_id": "sample-openai-1", "provider": "openai", "model": "gpt-live-1", "voice": "marin",
                 "language": "English", "audio_mode": "normal", "started_at": "2026-10-27T10:15:00+05:30",
                 "duration_s": round(c.t / 1000, 1), "form_name": "Program Feedback Survey (Test)", "form_completed": True},
        "transcript": c.transcript,
        "fields": fields(saved, expected, marks, active_extra=("sessions_attended_count", "children_ages")),
        "turn_metrics": c.turns, "tool_calls": c.tools,
        "usage": {"voice_seconds": round(c.t / 1000) + 15},
        "interruptions": 1, "events": c.events,
        "ratings": {"naturalness": 4, "clarity": 4, "pronunciation": 5, "accent_fit": 4, "politeness": 5},
        "scenario": {
            "id": "feedback-en-1", "name": "English happy path with a number correction",
            "caller_script": ["Hello", "Yes, go ahead.", "My name is Test Person One.", "I am thirty five.",
                              "Sample District.", "Yes I did.", "Fifteen sessions.", "No, I said fifteen, not fifty.",
                              "Two.", "Six.", "Six and nine.", "Four.", "No, nothing.", "Yes, that's fine.", "Yes, correct."],
            "expected_answers": expected,
        },
    }


def sarvam_sample():
    c = Call()
    split = lambda total: dict(stt=round(total * 0.25), llm=round(total * 0.45), tts=round(total * 0.30))
    c.caller("Namaste", latency=1100, **split(1100))
    c.agent("नमस्ते! मैं प्रोग्राम टीम से बोल रही हूँ। इसमें लगभग 3 मिनट लगेंगे। क्या अभी बात कर सकते हैं?")
    c.caller("हाँ, बोलिए।", latency=1050, **split(1050))
    c.agent("धन्यवाद। आपका नाम क्या है?")
    c.caller("मेरा नाम टेस्ट व्यक्ति दो है।", latency=1300, **split(1300)); c.save("caller_name", "टेस्ट व्यक्ति दो")
    c.agent("आपकी उम्र कितनी है?")
    c.caller("बयालीस साल।", latency=1250, **split(1250)); c.save("age", "42", parsed=42)
    c.agent("आप किस ज़िले में रहते हैं?")
    c.caller("Sample jila, haan vahi.", latency=1400, **split(1400)); c.save("district", "Sample District")
    c.agent("क्या आप प्रोग्राम के सेशन में आए थे?")
    c.caller("नहीं, नहीं आ पाया।", latency=1200, **split(1200)); c.save("attended_sessions", "no", parsed=False)
    c.agent("आप क्यों नहीं आ पाए?")
    c.caller("Kaam tha, time nahi mila.", latency=1350, **split(1350)); c.save("reason_not_attended", "Kaam tha, time nahi mila")
    c.agent("आपके कितने बच्चे हैं?")
    c.caller("Thirteen bachche hain.", latency=1600, **split(1600)); c.save("number_of_children", "13", parsed=13)
    c.agent("ठीक है, तेरह बच्चे। उनकी उम्र बताइए?")
    c.caller("Haan... chaar, saat aur das.", latency=1700, **split(1700))
    c.save("children_ages", "4, 7, 10", ok=False, error="Got 3 values but number_of_children is 13. Please confirm with the caller.")
    c.agent("आपने तेरह बच्चे बताए थे, सभी की उम्र बताइए?")
    c.caller("Bas teen hi hain.", latency=1900, **split(1900))
    c.agent("1 से 5 में, आप प्रोग्राम से कितने संतुष्ट हैं?")
    c.caller("चार।", latency=1150, **split(1150)); c.save("satisfaction_rating", "4", parsed=4)
    c.agent("क्या हम बाद में फिर से कॉल कर सकते हैं?")
    c.caller("हाँ।", latency=1100, **split(1100)); c.save("consent_to_followup", "yes", parsed=True)
    c.tool("complete_form", ok=False, result={"ok": False, "error": "Some required fields are missing.",
                                                 "missing_fields": [{"field_id": "children_ages"}]})
    c.agent("धन्यवाद, आपका दिन शुभ हो!")

    saved = {"caller_name": "टेस्ट व्यक्ति दो", "age": 42, "district": "Sample District", "attended_sessions": False,
             "reason_not_attended": "Kaam tha, time nahi mila", "number_of_children": 13,
             "satisfaction_rating": 4, "consent_to_followup": True}
    expected = {**saved, "number_of_children": 3, "children_ages": "4, 7, 10"}
    marks = {k: "correct" for k in saved}
    marks["number_of_children"] = "wrong"
    return {
        "call": {"call_id": "sample-sarvam-1", "provider": "sarvam", "model": "sarvam-cascade-test", "voice": "test-voice-hi",
                 "language": "Hindi", "audio_mode": "phone_8khz", "started_at": "2026-10-27T11:02:00+05:30",
                 "duration_s": round(c.t / 1000, 1), "form_name": "Program Feedback Survey (Test)", "form_completed": False},
        "transcript": c.transcript,
        "fields": fields(saved, expected, marks, active_extra=("reason_not_attended", "children_ages")),
        "turn_metrics": c.turns, "tool_calls": c.tools,
        "usage": {"stt_seconds": round(c.t / 1000 * 0.4), "llm_input_tokens": 18000, "llm_output_tokens": 1400,
                  "tts_characters": 1650},
        "interruptions": 0, "events": [],
        "ratings": {"naturalness": 4, "clarity": 3, "pronunciation": 4, "accent_fit": 5, "politeness": 5, "code_mixing": 4},
        "scenario": {
            "id": "feedback-hi-1", "name": "Hindi with Hinglish and a 'teen' number",
            "caller_script": ["Namaste", "हाँ, बोलिए।", "मेरा नाम टेस्ट व्यक्ति दो है।", "बयालीस साल।",
                              "Sample zila, haan wahi.", "नहीं, नहीं आ पाया।", "Kaam tha, time nahi mila.",
                              "Teen bachche hain.", "Haan chaar, saat aur das.", "Bas teen hi hain.", "चार।", "हाँ।"],
            "expected_answers": expected,
        },
    }


def gemini_sample():
    c = Call()
    c.caller("வணக்கம்", latency=950)
    c.agent("வணக்கம்! நான் திட்டக் குழுவிலிருந்து அழைக்கிறேன். இது சுமார் 3 நிமிடங்கள் ஆகும். பேசலாமா?")
    c.caller("சரி, சொல்லுங்கள்.", latency=900)
    c.agent("உங்கள் பெயர் என்ன?")
    c.caller("என் பெயர் சோதனை நபர் மூன்று.", latency=1100); c.save("caller_name", "சோதனை நபர் மூன்று")
    c.agent("உங்கள் வயது என்ன?")
    c.caller("இருபத்தெட்டு.", latency=1000); c.save("age", "28", parsed=28)
    c.agent("நீங்கள் எந்த மாவட்டத்தில் வசிக்கிறீர்கள்?")
    c.caller("மாதிரி மாவட்டம்.", latency=1050); c.save("district", "மாதிரி மாவட்டம்")
    c.agent("Did you attend any of the program sessions?")  # wrong language
    c.caller("ஆம், போனேன்.", latency=1200); c.save("attended_sessions", "yes", parsed=True)
    c.agent("எத்தனை அமர்வுகளில் கலந்து கொண்டீர்கள்?")
    c.caller("ஆறு.", latency=950); c.save("sessions_attended_count", "6", parsed=6)
    c.agent("உங்களுக்கு எத்தனை குழந்தைகள்?")
    c.caller("குழந்தைகள் இல்லை.", latency=1000); c.save("number_of_children", "0", parsed=0)
    c.agent("1 முதல் 5 வரை, திட்டத்தில் எவ்வளவு திருப்தி?")
    c.caller("ஐந்து.", latency=900); c.save("satisfaction_rating", "5", parsed=5)
    c.agent("பின்னர் மீண்டும் அழைக்கலாமா?")
    c.caller("வேண்டாம்.", latency=1050); c.save("consent_to_followup", "no", parsed=False)
    c.tool("complete_form", result={"ok": True})
    c.agent("நன்றி, நல்ல நாள்!")

    saved = {"caller_name": "சோதனை நபர் மூன்று", "age": 28, "district": "மாதிரி மாவட்டம்", "attended_sessions": True,
             "sessions_attended_count": 6, "number_of_children": 0, "satisfaction_rating": 5, "consent_to_followup": False}
    marks = {k: "correct" for k in saved}
    return {
        "call": {"call_id": "sample-gemini-1", "provider": "gemini", "model": "gemini-live-test", "voice": "test-voice-ta",
                 "language": "Tamil", "audio_mode": "normal", "started_at": "2026-10-27T12:30:00+05:30",
                 "duration_s": round(c.t / 1000, 1), "form_name": "Program Feedback Survey (Test)", "form_completed": True},
        "transcript": c.transcript,
        "fields": fields(saved, {}, marks, active_extra=("sessions_attended_count",)),
        "turn_metrics": c.turns, "tool_calls": c.tools,
        "usage": {"audio_in_tokens": 4200, "audio_out_tokens": 5100, "llm_input_tokens": 9000},
        "interruptions": 0, "events": [],
        "ratings": {"naturalness": 3, "clarity": 4, "pronunciation": 3, "accent_fit": 3, "politeness": 4},
        "scenario": None,
    }


def elevenlabs_sample():
    c = Call()
    c.agent("Hi! I'm calling from the program team for a short 3 minute feedback call. Is now a good time?", gap=300)
    c.caller("Sure.", latency=620)
    c.agent("Great. What's your name?")
    c.caller("Test Person Four.", latency=580); c.save("caller_name", "Test Person Four")
    c.agent("And your age?")
    c.caller("Fifty.", latency=640); c.save("age", "50", parsed=50)
    c.agent("Which district are you in?")
    c.caller("Sample District. You can also reach me on 98765 43210.", latency=700); c.save("district", "Sample District")
    c.agent("Thanks, I don't need a phone number. Did you attend any sessions?")
    c.caller("No.", latency=560); c.save("attended_sessions", "no", parsed=False)
    c.agent("May I ask why you couldn't attend?")
    c.caller("The timing did not suit me.", latency=610); c.save("reason_not_attended", "The timing did not suit me")
    c.agent("How many children do you have?")
    c.caller("One.", latency=590); c.save("number_of_children", "1", parsed=1)
    c.agent("How old is your child?")
    c.caller("Twelve.", latency=600); c.save("children_ages", "12", parsed=[12])
    c.agent("From 1 to 5, how satisfied are you with the")
    c.barge_in()
    c.caller("Three.", latency=650); c.save("satisfaction_rating", "3", parsed=3)
    c.agent("Any suggestion to improve the program?")
    c.caller("More evening sessions.", latency=630); c.save("improvement_suggestion", "More evening sessions")
    c.agent("Can we call you again later?")
    c.caller("Yes.", latency=570); c.save("consent_to_followup", "yes", parsed=True)
    c.tool("complete_form", result={"ok": True})
    c.agent("Thanks so much, have a lovely day!")

    saved = {"caller_name": "Test Person Four", "age": 50, "district": "Sample District", "attended_sessions": False,
             "reason_not_attended": "The timing did not suit me", "number_of_children": 1, "children_ages": [12],
             "satisfaction_rating": 3, "improvement_suggestion": "More evening sessions", "consent_to_followup": True}
    marks = {k: "correct" for k in saved}
    out = {
        "call": {"call_id": "sample-elevenlabs-1", "provider": "elevenlabs", "model": "eleven_realtime_v1_max",
                 "voice": "test-voice-en", "language": "English", "audio_mode": "phone_8khz",
                 "started_at": "2026-10-27T14:45:00+05:30", "duration_s": round(c.t / 1000, 1),
                 "form_name": "Program Feedback Survey (Test)", "form_completed": True},
        "transcript": c.transcript,
        "fields": fields(saved, {}, marks, active_extra=("reason_not_attended", "children_ages")),
        "turn_metrics": c.turns, "tool_calls": c.tools,
        "usage": {"voice_seconds": round(c.t / 1000), "llm_input_tokens": 12000, "llm_output_tokens": 900},
        "interruptions": 1, "events": c.events,
        "ratings": {"naturalness": 5, "clarity": 4, "pronunciation": 5, "accent_fit": 4, "politeness": 5},
        "scenario": None,
    }
    return out


def main():
    samples = {"openai": openai_sample(), "sarvam": sarvam_sample(), "gemini": gemini_sample(), "elevenlabs": elevenlabs_sample()}
    for name, data in samples.items():
        (HERE / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
