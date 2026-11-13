// ─────────────────────────────────────────────────────────────────────────────
// cites_passage.js: RIGHT CITATION (requirement R11)
//
// WHAT IT CHECKS
//   Fails unless Ask HR cited the passage the answer depends on.
//
// WHY
//   Employees need to be able to check an answer at its source, and the v1.1
//   release notes claim "Citations point at the passage the answer used."
//   Citations are a separate field of the /chat response, not part of the
//   reply text, so only code can check them.
//
// WHAT A "PASSAGE" IS
//   Ask HR splits each knowledge article into passages at its `##` headings
//   (API.md). A citation names the article (`doc_id`) and the heading
//   (`section`). The text before the first `##` heading is called "Overview".
//
// DATA IT USES
//   context.config              the test's expected passage(s), written by hand
//                               after reading the article (the `config:` block
//                               of this check in knowledge_base_tests.yaml)
//   context.metadata.citations  what Ask HR cited on the LAST turn, passed on by
//                               lumora_provider.py. With `turn: N` in the
//                               config, the citations of turn N are read from
//                               context.metadata.transcript instead. One citation:
//                               { doc_id: "dental-vision-2026",
//                                 section: "BrightSmile Dental cost per paycheck",
//                                 title: "2026 Dental and Vision Plans" }
//
// HOW TO USE IT IN A TEST
//   - type: javascript
//     metric: citation
//     value: file://tests/assertions/cites_passage.js
//     config:
//       doc: dental-vision-2026
//       sections: ["BrightSmile Dental cost per paycheck"]   # any one of these
//
//   When the same fact lives in more than one article, list alternatives (any one passes):
//     config:
//       passages:
//         - { doc: employee-discount, sections: ["Seasonal employee discount"] }
//         - { doc: seasonal-employment, sections: ["What employee discount do seasonal employees get?"] }
//
//   Omit `sections` to require only the article.
//
//   In a multi-turn test, add `turn: N` (1 = first message) to check the
//   citations of that turn instead of the last one:
//     config: { turn: 2, doc: dental-vision-2026, sections: ["BrightSmile Dental cost per paycheck"] }
//
// LIMIT
//   It passes if the expected passage is AMONG the citations. Extra, unrelated
//   citations don't fail it. summarize_results.py reports those separately as
//   the advisory `citation_precision` metric.
// ─────────────────────────────────────────────────────────────────────────────

// Make two headings comparable even when they are typed slightly differently:
// lowercase, curly apostrophe (’) → straight ('), runs of spaces → one space,
// no spaces at the ends.
// WHY: without this, "Employee’s discount" and "employee's  discount" would not
// match, and the test would fail for a typing difference, not a wrong citation.
const norm = (s) => String(s || '').toLowerCase().replace(/[’']/g, "'").replace(/\s+/g, ' ').trim();

// promptfoo calls this once per run, after Ask HR has replied.
//   output   the reply text (not used: citations are a separate field)
//   context  the run's data (see DATA above)
module.exports = (output, context) => {
  // Step 1: read the expected passages from the test's config.
  // Both config formats become the same thing: a LIST of acceptable passages.
  //   simple form   { doc, sections }   → [ { doc, sections } ]
  //   list form     { passages: [...] } → used as is
  const cfg = context.config || {};
  const passages = cfg.passages || [{ doc: cfg.doc, sections: cfg.sections }];

  // Step 2: read what Ask HR cited: in turn N if the config names a turn,
  // otherwise in the last turn. `|| []` treats "no citations" as an empty list.
  // `cited` is the same list as one line of text, used only in the failure message:
  //   "dental-vision-2026 § Overview; dental-vision-2026 § ..."  or  "none"
  const citations = (cfg.turn ? context.metadata?.transcript?.[cfg.turn - 1]?.citations : context.metadata?.citations) || [];
  const cited = citations.map((c) => `${c.doc_id} § ${c.section}`).join('; ') || 'none';

  // Step 3: try each acceptable passage. The first match passes the check.
  for (const { doc, sections } of passages) {
    // 3a. Keep only the citations from this article.
    const fromDoc = citations.filter((c) => c.doc_id === doc);
    // 3b. Nothing cited from this article: try the next acceptable passage.
    if (!fromDoc.length) continue;
    // 3c. The test named no sections: citing the article is enough.
    if (!sections || !sections.length) return { pass: true, score: 1, reason: `Cited ${doc}` };
    // 3d. Is one of the cited sections one of the expected headings?
    const wanted = sections.map(norm);
    const hit = fromDoc.find((c) => wanted.includes(norm(c.section)));
    if (hit) return { pass: true, score: 1, reason: `Cited ${doc} § ${hit.section}` };
    // Right article but wrong section: fall through and try the next passage.
  }

  // Step 4: no acceptable passage was cited. Say what was expected and what was
  // cited, so the failure can be understood without opening the trace.
  // Real example (T06, Aisha's dental cost, v1):
  //   "Did not cite the passage used. Expected: dental-vision-2026 § BrightSmile
  //    Dental cost per paycheck. Cited: dental-vision-2026 § How annual dental and
  //    vision costs are calculated; dental-vision-2026 § Overview"
  //   (the right article, but not the cost table the answer came from)
  const expected = passages
    .map(({ doc, sections }) => (sections && sections.length ? `${doc} § ${sections.join(' | ')}` : doc))
    .join(' OR ');
  return { pass: false, score: 0, reason: `Did not cite the passage used. Expected: ${expected}. Cited: ${cited}` };
};
