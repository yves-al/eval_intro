# Ask HR API

Lumora created a sandbox for Tamarack to evaluate Ask HR: you can supply any list of employees and knowledge articles, update certain settings, and chat with the assistant to see how it performs.

Base URLs come from your `.env`: `ASK_HR_BASE_URL` (v1) and `ASK_HR_V11_BASE_URL` (v1.1). Every endpoint below exists under both. Knowledge articles, settings, the employee list, conversations and HR cases belong to your session and are shared by both versions.

| Owner                       | Endpoints                        | What it means for you                                                                 |
| --------------------------- | -------------------------------- | ------------------------------------------------------------------------------------- |
| **Lumora's Ask HR sandbox** | `/chat`, `/conversations`        | Lumora's assistant chat interface and conversation history.                           |
|                             | `/docs`, `/config`, `/employees` | What the assistant runs on: knowledge articles, admin settings and the employee list. |
| **Tamarack**                | `/cases`                         | Tamarack's HR case queue, where Ask HR's escalations land.                            |
| Session                     | `/reset`, `/health`              | Your sandbox.                                                                         |

Every request except `/health` needs:

```
Authorization: Bearer $ASK_HR_API_KEY
Content-Type: application/json
```

Errors look like `{"error": {"code": "...", "message": "..."}}`. Codes: `401` missing or wrong key, `403` revoked session, `400` invalid request, `404` not found, `413` body too large (64 KiB; 512 KiB for `PUT /employees`), `429` `session_cap_reached` (10,000 chat requests per session), `502` `upstream_unavailable` (try again). Chat adds `400` `conversation_too_long` (a conversation holds up to 40 messages and 16,000 characters, Ask HR's replies included; start a new one).

## Chat and conversations

### `POST /chat`

Sends one user message and returns Ask HR's reply. Start one with `employee_id`, then send the returned `conversation_id` with every follow-up.

Start a conversation:

```json
{
  "employee_id": "E1012",
  "message": "How much PTO do I have?",
  "simulated_time": "2026-11-07T10:00:00-07:00"
}
```

Continue it:

```json
{
  "conversation_id": "conv_3b9e...",
  "message": "And how much will I have by the end of the year?"
}
```

| Field             | Required       | Notes                                                                                                                                                                                                                      |
| ----------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `employee_id`     | to start       | Any id in your session's employee list. Ask HR answers as that employee, with that employee's permissions. Fixed for the conversation.           |
| `message`         | yes            | The user's message, up to 16,000 characters.                                                                                                                                                                               |
| `conversation_id` | to continue    | From an earlier response. Leave it out to start a new conversation. Conversations belong to the version they started on; on the other base URL the id is unknown (`404`). |
| `simulated_time`  | no, start only | ISO 8601 timestamp with offset. The conversation's clock: it stays fixed for every message in the conversation. Without it, each message uses the real time. |
| `debug`           | no             | `true` adds `latency_ms` and `traces` to the response.                                                                                                                                                                     |

Response:

```json
{
  "conversation_id": "conv_3b9e...",
  "request_id": "req_8f2c...",
  "reply": "You have 88 hours of PTO as of October 24, 2026...",
  "citations": [
    {
      "doc_id": "pto-policy",
      "section": "Using PTO",
      "title": "Paid Time Off (PTO) Policy"
    }
  ],
  "case": null
}
```

- `citations`: the passages from knowledge articles the answer relies on.
- `case`: the HR case opened during this message, if any: `{"case_id", "category", "priority"}`.

With `"debug": true`, two more fields:

```json
{
  "conversation_id": "conv_3b9e...",
  "request_id": "req_8f2c...",
  "reply": "You have 88 hours of PTO as of October 24, 2026...",
  "citations": [
    {
      "doc_id": "pto-policy",
      "section": "Using PTO",
      "title": "Paid Time Off (PTO) Policy"
    }
  ],
  "case": null,
  "latency_ms": 1834,
  "traces": [
    {
      "type": "search",
      "source": "auto",
      "query": "How much PTO do I have?",
      "results": [{ "doc_id": "pto-policy", "section": "Using PTO", "rank": 1 }]
    },
    {
      "type": "tool_call",
      "name": "get_pto_balance",
      "arguments": {},
      "result": {
        "employee_id": "E1012",
        "as_of": "2026-10-24",
        "balance_hours": 88.0
      }
    }
  ]
}
```

`traces` lists everything Ask HR did for this message, in order:

- `search`: a search of the knowledge articles. `source` is `auto` for the search Ask HR runs before answering and `assistant` for an extra search it chose to run. `results` are the passages found, by rank.
- `tool_call`: a record lookup or action, with its arguments and result.

When you continue a conversation, send only `conversation_id`, `message` and `debug`; the employee and the clock come from the conversation. To compare versions, run the same messages as a new conversation on each base URL.

### `GET /conversations/{conversation_id}`

The whole conversation, turn by turn:

```json
{
  "conversation_id": "conv_3b9e...",
  "employee_id": "E1012",
  "version": "v1",
  "simulated_time": "2026-11-07T10:00:00-07:00",
  "created_at": "2026-11-08T17:02:11.524Z",
  "turns": [
    {
      "request_id": "req_8f2c...",
      "user": "How much PTO do I have?",
      "reply": "You have 88 hours of PTO...",
      "citations": [],
      "case": null
    }
  ]
}
```

`simulated_time` is `null` when the conversation runs on real time. Add `?debug=true` to include each turn's `latency_ms` and `traces`.

### `GET /conversations`

Your session's conversations on this version, newest first: `conversation_id, employee_id, created_at, updated_at, turns` (the number of turns).

## Knowledge articles (changeable)

| Endpoint                | Purpose                                                                                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /docs`             | All knowledge articles: `doc_id, title, status (published or archived), effective_date, audience, states, updated_by (vendor or session)`. Ask HR searches only `published` articles. |
| `GET /docs/{doc_id}`    | The article's current content (markdown).                                                                                                                                             |
| `PUT /docs/{doc_id}`    | Existing article: body `{"content": "...", "status": "published" or "archived"}`, either or both. New `doc_id`: creates an article (below).                                           |
| `DELETE /docs/{doc_id}` | Deletes an article you created. Articles that came with the sandbox can't be deleted; archive them instead.                                                                           |

To add an article, `PUT` a new `doc_id` (2 to 64 characters: lowercase letters, digits and hyphens, starting with a letter or digit):

```json
{
  "title": "Pet Bereavement Day",
  "content": "# Pet Bereavement Day\n\n## Pet loss\nEmployees may take one paid day when a household pet dies.",
  "effective_date": "2026-11-01",
  "audience": "all",
  "states": "all",
  "status": "published"
}
```

`title`, `content`, `effective_date`, `audience` (`all`, `managers` or `hr`) and `states` (`"all"` or a list from `CA, WA, CO, TX, NY`) are required; `status` defaults to `published`. A new article is searchable as soon as the `PUT` returns. Later `PUT`s on your own articles can change any of these fields.

Ask HR splits each article into passages at its `##` headings and searches the passages. Changes apply only to your session.

## Admin settings (changeable)

### `GET /config` and `PATCH /config`

```json
{
  "custom_instructions": "",
  "fallback_behavior": "answer_generally",
  "escalation_map": {
    "harassment_discrimination": { "category": "general", "priority": "low" },
    "safety_injury": { "category": "safety", "priority": "urgent" }
  }
}
```

| Field                 | Notes                                                                                                                                                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `custom_instructions` | Extra instructions Ask HR follows, up to 2,000 characters.                                                                                                                                                                             |
| `fallback_behavior`   | What Ask HR does when the knowledge articles do not cover a question: `answer_generally` or `decline_and_offer_case`.                                                                                                                  |
| `escalation_map`      | For each sensitive topic, the category and priority of the HR case Ask HR opens. Topics: `harassment_discrimination, safety_injury, accommodation_medical, immigration_work_authorization, payroll_error, benefits_unresolved, other`. |

`PATCH` accepts any subset of fields; `escalation_map` entries are merged by topic.

## Employees (changeable)

### `GET /employees` and `PUT /employees`

`GET` returns your session's employee list in the same format as `employees.json`. `PUT` with a list in that format replaces the whole list; Ask HR then answers as, looks up and applies policy to exactly those employees. Upload up to 1,000 employees (512 KiB).

To change an employee or add one, edit `employees.json` and upload the whole file. In Tamarack's HR system, employees write their own `note`.

The upload is checked as a whole; if anything is wrong, nothing changes and the `400` message names each employee and field. The main rules:

- Every field in `employees.json` is present, with no extra fields. `employee_id` is `E` plus 4 to 6 digits and unique; names are unique.
- `role` is `employee`, `manager` or `hr_partner`. `employment_type` is `salaried_ft` (40 hours), `hourly_ft` (30 to 60), `hourly_pt` (under 30) or `seasonal`.
- `location` is `Tamarack HQ`, `Fort Worth Distribution Center` or an existing store (`Boulder store`); remote employees are at `Tamarack HQ`. `work_state` is the location's state; `residence_state` is one of the five states; `timezone` is a valid time zone such as `America/Denver`.
- `hire_date` is no later than 2026-12-31. `manager_id` is null or another employee in the list, with `manager_name` matching; no reporting loops.
- Plans and coverage tier must fit the employee: none for part-time or seasonal employees, and Valley HMO only where it is offered. `k401_percent` is null for seasonal employees.
- `balances_as_of` is `2026-10-24`. Balances are non-negative; `pto_balance_hours` is null for seasonal employees.

## HR cases (Tamarack)

### `GET /cases`

Tamarack's HR case queue: cases Ask HR opened in your session, newest first: `case_id, employee_id, topic, category, priority, summary, version, request_id, created_at`.

Categories: `employee_relations, safety, accommodation, immigration, payroll, benefits, general`. Priorities: `urgent, high, normal, low`.

## Session

| Endpoint      | Purpose                                                                                                                                                                                                                |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /reset` | Body `{"scope": "cases"}` clears HR cases; `{"scope": "all"}` also restores knowledge articles, settings and the employee list to the session's starting state and deletes articles you created and all conversations. |
| `GET /health` | No key needed. `{"ok": true}`.                                                                                                                                                                                         |

## Quick check

```sh
set -a; source .env; set +a
curl -s "$ASK_HR_BASE_URL/chat" \
  -H "Authorization: Bearer $ASK_HR_API_KEY" -H "Content-Type: application/json" \
  -d '{"employee_id":"E1012","message":"How much PTO do I have?","debug":true}'
```
