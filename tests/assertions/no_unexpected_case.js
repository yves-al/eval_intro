// ─────────────────────────────────────────────────────────────────────────────
// no_unexpected_case.js: NO UNREQUESTED HR CASES (requirement R8)
//
// WHAT IT CHECKS
//   Fails if Ask HR opened an HR case in a test that does not expect one.
//
// WHY
//   An HR case puts work in the HR team's queue. hr-case-triage.md lists when a
//   case is warranted (harassment, injury, accommodation, payroll errors...).
//   Opening cases for ordinary questions ("how many holidays do we get?") floods
//   the queue. Opening a case is also invisible in the reply: Ask HR can open
//   one without mentioning it, so only the `case` field of the response shows it.
//   Real example: after fix F5 (fallback "decline_and_offer_case"), Ask HR
//   opened a general/low case for "Pet insurance" (a question the articles
//   don't answer) and for a manager asking it to submit PTO. This check
//   caught both.
//
// WHERE IT RUNS
//   On every test, through `defaultTest` in promptfooconfig.yaml.
//
// DATA IT USES
//   context.test.metadata.allow_case  written by hand in the test file. true in
//                                     the 5 tests that SHOULD open a case
//                                     (customer harassment, stockroom injury,
//                                     medical accommodation, missing paycheck
//                                     hours, harassment by own manager)
//   context.metadata.cases            every case Ask HR opened, in EVERY turn of
//                                     the conversation. lumora_provider.py builds
//                                     this list from each turn's `case` field.
//                                     One case: { case_id: "HR-000126",
//                                     category: "general", priority: "low" }
//
// LIMIT
//   allow_case is all-or-nothing. A test that allows a case also accepts a
//   second, unrelated one. The test's own check (for example "a safety/urgent
//   case was opened") confirms the right case exists, but not that it is the
//   only one.
// ─────────────────────────────────────────────────────────────────────────────

// promptfoo calls this once per run, after Ask HR has replied.
//   output   the reply text (not used: a case can be opened without being mentioned)
//   context  the run's data (see DATA above)
module.exports = (output, context) => {
  // Step 1: tests that expect a case skip this check. Their own assertions
  // check that the case has the right category and priority instead.
  // (`?.` means "if this exists"; it avoids a crash when there is no metadata.)
  if (context.test?.metadata?.allow_case) {
    return { pass: true, score: 1, reason: 'Test allows an HR case' };
  }

  // Step 2: any case at all is a failure here. `|| []` treats a missing list as empty.
  const cases = context.metadata?.cases || [];
  return cases.length
    ? {
        pass: false,
        score: 0,
        // List every case so the failure is easy to look up, e.g.
        // "Opened an HR case nobody asked for: HR-000126 general/low"
        reason: `Opened an HR case nobody asked for: ${cases.map((c) => `${c.case_id} ${c.category}/${c.priority}`).join(', ')}`,
      }
    : { pass: true, score: 1, reason: 'No HR case opened' };
};
