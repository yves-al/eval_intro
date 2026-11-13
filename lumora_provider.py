import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

RETRYABLE_STATUS = {502}
MAX_ATTEMPTS = 3


def _post_chat(base_url, headers, payload):
    """POST /chat, retrying on 502 upstream_unavailable and on dropped connections.
    Returns (ok, data_or_error)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(base_url + "/chat", json=payload, headers=headers, timeout=120)
        except requests.ConnectionError:
            # The sandbox sometimes closes the connection without answering. A long
            # conversation sends many requests per run, so one drop would lose the run.
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 * attempt)
                continue
            raise
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}
        if resp.ok:
            return True, data
        if resp.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
            time.sleep(2 * attempt)
            continue
        return False, f"Ask HR returned {resp.status_code}: {data}"


def call_api(prompt, options, context):
    """promptfoo provider for Lumora's Ask HR.

    Every test gets its own new conversation. For multi-turn tests, set the
    `turns` var to a list of earlier user messages: they are sent first, in
    order, in the same conversation, and the test's prompt is the final turn
    that gets graded.

    Test vars:
      employee_id     who is asking (default E1010)
      turns           optional list of earlier user messages
      simulated_time  optional ISO 8601 clock for the conversation

    Provider config (promptfooconfig.yaml, under `config:`):
      base_url        explicit base URL, or
      base_url_env    name of the env var holding it (default ASK_HR_BASE_URL)
    """
    vars = context.get("vars", {}) or {}
    config = options.get("config", {}) or {}

    base_url = config.get("base_url") or os.environ.get(config.get("base_url_env", "ASK_HR_BASE_URL"), "")
    base_url = base_url.rstrip("/")
    if not base_url:
        return {"error": "No base URL: set ASK_HR_BASE_URL in .env or base_url / base_url_env in the provider config"}

    api_key = os.environ.get("ASK_HR_API_KEY")
    if not api_key:
        return {"error": "ASK_HR_API_KEY is not set (check your .env)"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    employee_id = vars.get("employee_id", "E1010")
    # `turns` must be a JSON string in the test file: promptfoo expands list-valued
    # vars into one test per item, which would split the conversation apart.
    turns = vars.get("turns") or []
    if isinstance(turns, str):
        turns = json.loads(turns) if turns.strip().startswith("[") else [turns]
    messages = list(turns) + [prompt]

    conversation_id = None
    cases = []
    transcript = []
    all_traces = []
    data = {}

    try:
        for i, message in enumerate(messages):
            payload = {"message": message, "debug": True}
            if conversation_id:
                payload["conversation_id"] = conversation_id
            else:
                payload["employee_id"] = employee_id
                if vars.get("simulated_time"):
                    payload["simulated_time"] = vars["simulated_time"]

            ok, data = _post_chat(base_url, headers, payload)
            if not ok:
                return {"error": f"Turn {i + 1}: {data}"}

            conversation_id = data.get("conversation_id", conversation_id)
            if data.get("case"):
                cases.append(data["case"])
            # Every turn's traces, tagged with the turn number (1-based), so trace
            # checks such as no_unauthorized_lookups.js can see earlier turns too.
            all_traces += [{**t, "turn": i + 1} for t in (data.get("traces") or [])]
            # Per-turn record, so a check can grade any turn, not only the last:
            # its reply, its citations and the HR case it opened (if any).
            transcript.append({
                "user": message,
                "reply": data.get("reply"),
                "citations": data.get("citations") or [],
                "case": data.get("case"),
            })

        return {
            "output": data.get("reply", json.dumps(data)),
            "metadata": {
                "conversation_id": conversation_id,
                "employee_id": employee_id,
                # Final turn only
                "citations": data.get("citations") or [],
                "case": data.get("case"),
                "traces": data.get("traces") or [],
                "latency_ms": data.get("latency_ms"),
                # Every turn of the conversation
                "cases": cases,  # every HR case opened, in any turn
                "all_traces": all_traces,  # traces of every turn, each with "turn"
                "transcript": transcript,  # [{user, reply, citations, case}] per turn
            },
        }

    except Exception as e:
        return {"error": f"API sequence failed: {str(e)}"}
