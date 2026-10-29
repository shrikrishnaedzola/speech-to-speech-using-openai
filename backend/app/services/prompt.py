"""Build agent instructions from the selected form and language.

Nothing about the survey is hard-coded here: fields, order, rules and
language all come from the form JSON and the UI selection.

Two shapes:
- realtime_instructions(): one prompt for gpt-realtime-2.1, which calls tools itself.
- live_instructions() + live_backend_instructions(): GPT-Live talks to the caller
  and hands tool work to a delegated Responses model ("backend"). See
  https://developers.openai.com/api/docs/guides/live-delegation and
  https://developers.openai.com/api/docs/guides/live-prompting
"""
from . import form_logic

BASE_RULES = """You are a polite, friendly survey assistant calling on behalf of an NGO program. Speak in {language}. Keep sentences short and simple.
- Greet the caller, explain the call takes about 3 minutes, and ask if it is a good time to talk.
- Ask ONE question at a time, in the order of the form.
- Ask follow-up questions only when the form rules say so.
- If an answer is unclear or out of range, politely ask again.
- If the caller corrects an earlier answer, update it.
- Before ending, read back the key answers briefly and ask the caller to confirm.
- Never ask for phone numbers, ID numbers, bank details or addresses.
- If the caller wants to stop, thank them and end politely."""


def describe_field(field: dict) -> str:
    """One line per field, e.g. '- age (number 18-100, required): How old are you?'"""
    kind = field["type"]
    if kind == "number" and ("min" in field or "max" in field):
        kind += f" {field.get('min', '')}-{field.get('max', '')}"
    if kind == "choice":
        kind += ": " + " / ".join(field["choices"])
    if kind == "list_number" and field.get("count_field"):
        kind = f"list of numbers, count must equal {field['count_field']}"
    flags = "required" if field.get("required") else "optional"
    line = f"- {field['id']} ({kind}, {flags}): \"{field.get('question', field.get('label'))}\""
    if field.get("condition"):
        line += f" -- ask ONLY if {form_logic.describe_condition(field['condition'])}"
    return line


def form_section(form: dict) -> str:
    lines = "\n".join(describe_field(f) for f in form["fields"])
    return (
        f"# Form: {form['name']}\n"
        "Ask the questions in this order. Translate each question naturally into the call language.\n"
        f"{lines}"
    )


TOOL_RULES = """# Saving answers
- After each answer, call save_answer right away. Do not wait until the end.
- Send value as text: numbers as digits ("34"), yes/no as "yes" or "no", lists as "4, 7". Translate the caller's words to these forms.
- Use confidence "low" if you are not sure you heard correctly.
- If a tool result has "ok": false, explain the problem simply and ask the question again.
- The tool result "next" tells you the next question to ask.
- Use request_clarification when an answer is unclear; use skip_field only for optional questions the caller declines.
- After the caller confirms the read-back, call complete_form. If it lists missing fields, ask them."""


def realtime_instructions(form: dict, language: str) -> str:
    return "\n\n".join([BASE_RULES.format(language=language), form_section(form), TOOL_RULES])


def live_instructions(form: dict, language: str) -> str:
    """Instructions for the GPT-Live conversation model (uses the recommended template headings)."""
    return "\n\n".join([
        "# Personality\n" + BASE_RULES.format(language=language),
        "Speak first only after the caller says hello.",
        form_section(form),
        "# Backchannel policy\nUse short acknowledgements like \"okay\" or \"thank you\". Do not repeat every answer back.",
        "# Interruption policy\nIf the caller interrupts, stop and listen. Answer them, then return to the current question.",
        "# Delegation policy\n"
        "The backend saves every answer and checks it against the form rules.\n"
        "- Every time the caller answers a form question or corrects an answer, Generate <|SpawnThinking|>.\n"
        "- When the caller confirms the final read-back, Generate <|SpawnThinking|> to complete the form.\n"
        "- Wait for the backend result before moving on. If it says the answer is invalid, explain simply and ask again.\n"
        "- Do not guess whether an answer was saved.",
    ])


def live_backend_instructions(form: dict, language: str) -> str:
    """Instructions for the delegated Responses model that calls our tools."""
    return "\n\n".join([
        "You are the data-saving backend for a voice survey call. A voice assistant is talking to the caller "
        f"in {language}. Read the latest caller answer from the conversation and call the right tool.",
        form_section(form),
        TOOL_RULES,
        "# Your reply\nAfter the tool result, reply with ONE short sentence in English telling the voice assistant "
        "what to do next: the next question to ask, or what to re-ask and why. Never invent values.",
    ])
