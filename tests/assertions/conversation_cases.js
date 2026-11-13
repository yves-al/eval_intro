// ─────────────────────────────────────────────────────────────────────────────
// conversation_cases.js: THE RIGHT HR CASE, IN THE RIGHT TURN (requirements R6, R8)
//
// WHAT IT CHECKS
//   In a multi-turn conversation, each turn opens exactly the HR case it should
//   and nothing else:
//     - a turn listed in `expect` must open a case with that category and priority
//     - every other turn must open no case at all
//
// WHY
//   no_unexpected_case.js (run on every test) can only say yes or no for the
//   whole test: with `allow_case: true` it accepts any case, in any turn. In a
//   long conversation with one sensitive message among ordinary questions,
//   that is too loose. A case opened for the pet-insurance question would go
//   unnoticed as long as the injury also opened one. This check pins each case
//   to its turn.
//
// HOW TO USE IT IN A TEST
//   Set `allow_case: true` in the test's metadata (so the global yes/no check
//   steps aside), then:
//     - type: javascript
//       metric: escalation
//       value: file://tests/assertions/conversation_cases.js
//       config:
//         expect:
//           - { turn: 10, category: safety, priority: urgent }
//   With `expect: []`, no turn may open a case.
//
// DATA IT USES
//   context.config.expect          the expected cases, written by hand from
//                                  knowledge-articles/hr-case-triage.md
//   context.metadata.transcript    one entry per turn, built by lumora_provider.py:
//                                  { user, reply, citations, case }
//                                  `case` is the case that turn opened, or null:
//                                  { case_id: "HR-000131", category: "safety", priority: "urgent" }
// ─────────────────────────────────────────────────────────────────────────────

// Write a case as "HR-000131 safety/urgent" for the failure message.
const show = (c) => `${c.case_id} ${c.category}/${c.priority}`;

// promptfoo calls this once per run, after the whole conversation.
//   output   the last reply (not used: cases are a separate field)
//   context  the run's data (see DATA above)
module.exports = (output, context) => {
  const expect = context.config?.expect || [];
  const transcript = context.metadata?.transcript || [];
  const problems = [];

  // Step 1: a listed turn that doesn't exist means the test is wrong (for
  // example a turn was removed from the conversation). Say so instead of
  // silently passing.
  for (const e of expect) {
    if (e.turn < 1 || e.turn > transcript.length) problems.push(`turn ${e.turn} is not in the ${transcript.length}-turn conversation`);
  }

  // Step 2: go through the conversation one turn at a time (turn = index + 1).
  transcript.forEach((entry, i) => {
    const turn = i + 1;
    const opened = entry.case; // the case this turn opened, or null
    const wanted = expect.find((e) => e.turn === turn);

    if (wanted && !opened) {
      // A sensitive message that should have reached HR did not.
      problems.push(`turn ${turn}: expected a ${wanted.category}/${wanted.priority} case, none opened`);
    } else if (wanted && (opened.category !== wanted.category || opened.priority !== wanted.priority)) {
      // A case was opened, but it would go to the wrong team or at the wrong speed.
      problems.push(`turn ${turn}: expected ${wanted.category}/${wanted.priority}, opened ${show(opened)}`);
    } else if (!wanted && opened) {
      // A case nobody needed: work in HR's queue for an ordinary question.
      problems.push(`turn ${turn}: opened ${show(opened)} nobody asked for ("${String(entry.user).slice(0, 60)}")`);
    }
  });

  // Step 3: the verdict, listing every problem so the run is easy to diagnose.
  return problems.length
    ? { pass: false, score: 0, reason: `HR cases: ${problems.join('; ')}` }
    : {
        pass: true,
        score: 1,
        reason: expect.length ? `HR cases as expected in turn(s) ${expect.map((e) => e.turn).join(', ')}, none elsewhere` : 'No HR case opened in any turn',
      };
};
