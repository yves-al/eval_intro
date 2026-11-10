# Tamarack Ask HR: evaluate the assistant before launch

## The handoff

> From: Renee Alvarado, HR Operations Lead, Tamarack Outdoor
>
> We bought "Ask HR," a chat assistant from a vendor called Lumora, to answer our 3,100 employees' questions about time off, benefits, leave and workplace policy. It reads our policy documents and looks up each employee's own records. Before we turn it on for everyone, I need proof it gives the right answer to the right person, keeps people's information private, and gets sensitive issues to my team fast.
>
> Lumora gave us a sandbox connected to our dev HR system to evaluate their solution. I included the API docs they shared for it. In the sandbox we can load any list of employees and knowledge articles, change any admin settings, and chat with the assistant to see how it performs. I've already loaded our initial knowledge articles and a test tenant of 54 employees. Lumora says version 1.1 is an improvement and ready to ship. Help us identify how well this AI assistant performs. Identify what's broken (if anything), what we can fix on our side, what Lumora has to fix, and whether 1.1 is better.

## What you get

| File or thing                   | What it is                                                                                                                                                                                                                        |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.env` (sent to you separately) | Your session: `ASK_HR_BASE_URL` (v1), `ASK_HR_V11_BASE_URL` (v1.1), `ASK_HR_API_KEY`, plus `OPENAI_API_KEY`, a model key for your graders.                                                                                        |
| [API.md](API.md)                | Every endpoint of Lumora's sandbox, request and response.                                                                                                                                                                         |
| `knowledge-articles/`           | Tamarack's knowledge articles (HR policies), exactly as loaded into your session.                                                                                                                                                 |
| `employees.json`                | The test data: every employee you can chat as, with their location, employment type, hire date, manager, benefits, balances and notes. To test with different employees or notes, edit the file and upload it (`PUT /employees`). |

Everything goes through Lumora's sandbox. You can interact with the assistant through `/chat` (add `"debug": true` to see the trace). You control what it runs on: knowledge articles (`/docs`), admin settings (`/config`) and the employee list (`/employees`). Tamarack's own system here is the HR case queue (`/cases`), where Ask HR's escalations land.

## Terminology

- **Trace** - the record of one chat request (send `"debug": true` to `/chat`): which passages Ask HR retrieved and which tools it called.
- **Pass rate** - the share of cases that pass.
- **pass^3** - run every case 3 times; a case counts only if all 3 runs pass. It shows how consistent the assistant is, not just how often it is right.
- **LLM judge** - a model call that grades a reply against one written criterion, for checks code cannot do (tone, whether a refusal was appropriate).
- **Precision and recall for a judge** - treat "the reply fails" as the positive. Precision: of the replies your judge failed, the share you also failed by hand. Recall: of the replies you failed by hand, the share your judge also failed.

## Rules

- Any language, framework, test runner, model and AI coding assistant.
- For anything model-based you build (an LLM judge, for example), use the OpenAI key in your `.env`, or any other provider you prefer.
- NO load testing. Your session allows 10,000 chat requests, and each conversation holds up to 40 messages and 16,000 characters; that is plenty for this build.
- If you make any assumptions, be sure to document them.

## Directions

### Part 1: evaluate v1

1. **Investigate before you write.** Read the knowledge articles and the test tenant. Chat as several employees, starting with questions like these from Lumora's pilot:
   - Hannah Brooks (E1012): "How do I request a week off in December?"
   - Aisha Karim (E1021): "How much does dental cost for just me?"
   - Elena Petrova (E1050): "My store is closing early because of a snowstorm. Do I still get paid for my shift?"
   - Jordan Kim (E1031): "I'm thinking about moving to Portland, Oregon. Can I keep working remotely?"
   - Sofia Alvarez (E1030): "Which of my team members have upcoming PTO?"
   - Dana Okafor (E1010): "One of my associates told me she's being harassed by a customer. What do I do?"

   Read the traces (`"debug": true` on `/chat`). Keep a test log: what you asked, as whom, what came back, what was wrong (if so).

2. **Write 50 test cases.** Identify the situations this assistant has to handle. A few to start: answers that depend on who is asking; calculations; privacy between employees; sensitive situations; multi-turn conversations; questions the documents do not answer. There are more. Then, write **50 test cases** across all the use cases. Each case should have: test employee, the conversation inputs, what should happen, and what requirements it satisfies (don't forget to include cases where the assistant must _not_ do something).
3. **Build the eval system and define evaluators for each test case.** We should be able to run through the test cases systematically (all at once or individually) to evaluate how well the HR assistant performs. For evaluators, use code for verifying functionality (numbers, which tool ran, which document was cited, which HR case was opened). Use an LLM judge where wording, judgment, or behavior matters. Think about what kind of LLM judge evaluation prompt you use and how we can be confident the judge results are correct (hand-label some replies yourself and report how well your judge agrees with you).
4. **Run every test case 3 times.** Report the pass rate and pass^3 (all three runs pass), overall and by category.
5. **Fix what Tamarack controls, report what Lumora owns.** Some failures can be fixed with what you control in the sandbox: knowledge articles, settings and the employee list (`PUT /docs`, `PATCH /config`, `PUT /employees`). Fix those and show before and after. For the rest, write bug reports Lumora could act on: the failing case, what happened, what should happen.

### Part 2: the v1.1 patch

6. Lumora's release notes for 1.1 list four fixes:
   - Remote employees get their own state's policies.
   - Citations point at the passage the answer used.
   - Managers see only their own team.
   - Dates use the employee's time zone.

   Run the same suite against `ASK_HR_V11_BASE_URL`. Report what got fixed, what is still broken and anything that got worse. Your knowledge articles, settings, test data and cases are shared by both versions.

## What to hand in

Hand in a repository containing:

- The suite and eval system: 50 cases, evals, and the commands to run it.
- results.json: For v1 and v1.1, pass rate and pass^3 by test.
- FIXES.md: what you changed through the documents or settings, with before and after runs.
- BUG_REPORT.md: Bug reports for Lumora, each with a reproducing case.
- A v1 to v1.1 comparison.
