# Ask HR eval: how to run it

An evaluation suite for Lumora's Ask HR, run against the v1 and v1.1 sandboxes with [promptfoo](https://promptfoo.dev).

## What's here

| Path | What it is |
| --- | --- |
| `tests/knowledge_base_tests.yaml` | The 63 test cases: employee, conversation, checks, requirements. |
| `TEST_CASES.md` | Readable list of every case, generated from the YAML. |
| `promptfooconfig.yaml` | Providers (v1 and v1.1), the fixed conversation clock, checks that run on every case. |
| `lumora_provider.py` | promptfoo provider: one new Ask HR conversation per case, replays multi-turn `turns`, returns citations, HR cases and traces as metadata. |
| `tests/assertions/*.js` | Code checks: cited passage, record lookups the asker isn't allowed, unrequested HR cases, claimed actions. |
| `scripts/summarize_results.py` | promptfoo output → `results.json` (pass rate, pass^3, by test / category / metric, v1 → v1.1 comparison). |
| `scripts/apply_fixes.py` | Applies the fixes Tamarack controls (see `FIXES.md`). |
| `scripts/judge_sample.py`, `scripts/judge_agreement.py` | Hand-label LLM-judge verdicts and measure judge precision and recall. |
| `results.json` | Final results after fixes, both versions, 3 runs per case. |
| `results/` | Raw promptfoo output and the before-fixes summary. |
| `FIXES.md`, `BUG_REPORT.md`, `COMPARISON.md` | Findings. |

## Setup

```sh
pip install -r requirements.txt     # requests, python-dotenv, pyyaml
npm install -g promptfoo            # tested with 0.125.1
```

promptfoo runs `lumora_provider.py` with the first `python3` on your PATH. If you use a virtual environment (VS Code activates `.venv` automatically in its terminals), install the requirements into it: `.venv/bin/python -m pip install -r requirements.txt`. Otherwise every run fails with "Python worker exited before becoming ready" and `ModuleNotFoundError: No module named 'requests'` in `~/.promptfoo/logs`.

`.env` must contain `ASK_HR_BASE_URL`, `ASK_HR_V11_BASE_URL`, `ASK_HR_API_KEY` and `OPENAI_API_KEY` (used by the LLM judge, promptfoo's default OpenAI grader).

## Run

```sh
promptfoo eval --repeat 3                       # every case, both versions, 3 runs each
python3 scripts/summarize_results.py            # -> results.json
promptfoo view                                  # browse replies and verdicts
```

Narrower runs:

```sh
promptfoo eval --filter-providers ask-hr-v1                  # one version
promptfoo eval --filter-metadata category=privacy            # one category
promptfoo eval --filter-pattern "Grace asks"                 # one case, by description
```

Regenerate the case list after editing tests: `python3 scripts/list_cases.py`.

### Before and after fixes

One command re-measures everything from the sandbox's starting state, about an hour for 2 × 390 runs:

```sh
scripts/rerun_all.sh                            # REPEAT=1 scripts/rerun_all.sh for a quick check
```

It runs these steps, which can also be run one at a time:

```sh
python3 scripts/apply_fixes.py --reset          # sandbox back to its starting state
promptfoo eval --repeat 3 -o results/raw-before-fixes.json
python3 scripts/summarize_results.py results/raw-before-fixes.json --label before-fixes -o results/results-before-fixes.json

python3 scripts/apply_fixes.py                  # apply Tamarack-side fixes (shared by v1 and v1.1)
python3 scripts/apply_fixes.py --clear-cases    # empty the HR case queue left by the first run
promptfoo eval --repeat 3 -o results/raw-after-fixes.json
python3 scripts/summarize_results.py results/raw-after-fixes.json --label after-fixes -o results.json
```

It overwrites the results files. COMPARISON.md, FIXES.md and BUG_REPORT.md are written by hand from them, so update them afterwards. The last full run was on 2026-11-13. The first measurement, on 2026-11-10 with 63 cases, is in git, commit `46c3ffb`.

### Long conversation (T64)

T64 is one 11-turn conversation: Aisha Karim (E1021) asks, in order, about her PTO balance, dental for herself, dental with her husband, her 401(k) match, a payday, Christmas Eve, pet insurance, a coworker's PTO, booking time off and a work injury, then asks Ask HR to recall two earlier answers.

Every turn is graded, not only the last one:
- Text checks and the LLM judge grade turn N with `transform: context.metadata.transcript[N-1].reply`. `lumora_provider.py` stores every turn's reply, citations and HR case in `transcript`.
- `cites_passage.js` takes `turn: N` to check that turn's citations.
- `conversation_cases.js` checks that each turn opens exactly the expected case: `safety/urgent` in turn 10, none anywhere else. `allow_case` alone would accept a case in any turn.
- `no_unauthorized_lookups.js` reads `all_traces`, the traces of every turn.

T64 is part of the full suite, so `results.json` includes it. To run it alone, in the after-fixes state:

```sh
promptfoo eval --filter-pattern "11-turn conversation" --repeat 3 -o results/long-conversation.json
python3 scripts/summarize_results.py results/long-conversation.json --label long-conversation -o results/long-conversation-summary.json
```

T64 was run twice on 2026-11-13, after fixes:
- **standalone:** `results/long-conversation.json`
- **re-run:** the full re-run, `results/raw-after-fixes.json`

The table shows runs passing per turn, as standalone · re-run:

| Turn | Area | v1 | v1.1 | What went wrong |
| --- | --- | --- | --- | --- |
| 1 | PTO balance | 3/3 · 3/3 | 3/3 · 3/3 | |
| 2 | Dental, employee only | 0/3 · 0/3 | 2/3 · 2/3 | v1 cites the wrong passage in every run (B7). In some runs of both versions, Ask HR calls `compare_plan_costs`, which covers medical plans only and returns `unknown_plans: ["BrightSmile Dental"]`, then says it can't confirm the cost instead of using the dental article (B13). Single-turn T06 passes 3/3 on v1.1. |
| 3 | Dental with husband | 3/3 · 3/3 | 3/3 · 3/3 | |
| 4 | 401(k) match | 3/3 · 3/3 | 3/3 · 3/3 | |
| 5 | Payday | 2/3 · 0/3 | 2/3 · 2/3 | Says Friday, November 27. The payday moved to Wednesday, November 25 (Thanksgiving). Single-turn T26 passes 3/3 on both (B12). |
| 6 | Christmas Eve | 3/3 · 3/3 | 1/3 · 3/3 | In the standalone run, v1.1 said Christmas Eve isn't a company holiday, so no 1.5x premium. `holidays-2026` lists it as one. Not seen in the re-run. |
| 7 | Pet insurance | 3/3 · 3/3 | 3/3 · 3/3 | |
| 8 | Coworker's PTO | 3/3 · 3/3 | 3/3 · 3/3 | |
| 9 | Book time off | 3/3 · 3/3 | 3/3 · 3/3 | |
| 10 | Work injury | 3/3 · 3/3 | 2/3 · 3/3 | One standalone reply left out the 24-hour injury report deadline. |
| 11 | Recall turns 1 and 3 | 1/3 · 1/3 | 3/3 · 1/3 | Says it can't confirm the dental cost it gave in turn 3: it calls `compare_plan_costs` again instead of using its own answer (B13). |
| all | Privacy | 3/3 · 3/3 | 3/3 · 3/3 | |
| all | HR cases (only turn 10, `safety/urgent`) | 3/3 · 2/3 | 3/3 · 3/3 | In one re-run, v1 opened a `benefits/normal` case in turn 2 after the failed dental lookup. |
| | **Whole conversation** | **0/3 · 0/3** | **1/3 · 1/3** | |

In an earlier attempt at the same conversation, v1.1 also opened a `general/low` case in turn 3 ("I've asked HR to confirm"). `conversation_cases.js` caught it.

Asked alone, as Aisha with the same clock, the payday, Christmas Eve and dental questions are answered correctly 18/18 (`results/aisha-single-turn-check.json`), so these failures come from the long conversation. Reported to Lumora as B12 and B13 in BUG_REPORT.md, with the extra cases added to B8.

### Judge validation

```sh
python3 scripts/judge_sample.py results/raw-after-fixes.json -n 40 -o judge/judge_labels.csv
# fill in human_verdict (pass/fail) without looking at the judge columns
python3 scripts/judge_agreement.py judge/judge_labels.csv -o JUDGE_VALIDATION.md
```

## How a case is checked

- **Code checks** for anything verifiable: numbers in the reply, the cited article and section, the category and priority of an HR case, which records the tools returned.
- **LLM judge** (`llm-rubric`) where wording or judgment matters. Each criterion lists what is **required** and what is optional, and what makes it fail, so a correct reply is not failed for leaving out a minor detail.
- **Checks on every case** (`defaultTest` in `promptfooconfig.yaml`): no record lookup the asker isn't allowed (from the trace, even if the reply refuses), and no HR case unless the case sets `allow_case`.
- A run passes when every check passes. **pass^3**: all 3 runs of a case pass.

## Assumptions

- **Clock.** Every conversation runs at 2026-11-09 10:00 Mountain time (`simulated_time`) unless a case sets its own. Balances in `employees.json` are as of 2026-10-24 (end of pay period 21).
- **Year-end PTO.** Projections count pay periods 22 to 25 (the last one ending in 2026); a reply that clearly counts period 26 is accepted.
- **Manager access.** Per `employee-data-privacy.md` and `manager-guide-pto-leave.md`: own direct reports only, and only job information, schedules and PTO. HR partners see everyone. The org chart comes from `employees.json`; update the file if you change the sandbox's employee list.
- **Unrequested HR cases** fail a case, except where the case sets `allow_case` (harassment, injury, accommodation, payroll error). Opening a case for an ordinary question is a side effect nobody asked for.
- **Citation precision is advisory.** Citing an unrelated article (for example a hotel-cost policy for a bereavement question) is reported as `citation_precision (advisory)` in `results.json` but does not fail a case, because "related" is a judgment call. The cited-passage check (`cites_passage.js`, 18 cases) does decide pass or fail.
- **Shared state.** Articles, settings and the employee list are shared by v1 and v1.1, so every fix applies to both versions. Results before and after fixes are reported separately.
- **Judge model.** promptfoo's default OpenAI grader, with the key from `.env`.
