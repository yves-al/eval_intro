// Fails unless the reply cites the passage the answer depends on.
// A citation's `section` is the article's `##` heading ("Overview" = the intro).
//
// Usage in a test:
//   - type: javascript
//     metric: citation
//     value: file://tests/assertions/cites_passage.js
//     config:
//       doc: dental-vision-2026
//       sections: ["BrightSmile Dental cost per paycheck"]   # any one of these
//
// When the same fact lives in more than one article, list alternatives (any one passes):
//     config:
//       passages:
//         - { doc: employee-discount, sections: ["Seasonal employee discount"] }
//         - { doc: seasonal-employment, sections: ["What employee discount do seasonal employees get?"] }
//
// Omit `sections` to require only the article.

const norm = (s) => String(s || '').toLowerCase().replace(/[’']/g, "'").replace(/\s+/g, ' ').trim();

module.exports = (output, context) => {
  const cfg = context.config || {};
  const passages = cfg.passages || [{ doc: cfg.doc, sections: cfg.sections }];
  const citations = context.metadata?.citations || [];
  const cited = citations.map((c) => `${c.doc_id} § ${c.section}`).join('; ') || 'none';

  for (const { doc, sections } of passages) {
    const fromDoc = citations.filter((c) => c.doc_id === doc);
    if (!fromDoc.length) continue;
    if (!sections || !sections.length) return { pass: true, score: 1, reason: `Cited ${doc}` };
    const wanted = sections.map(norm);
    const hit = fromDoc.find((c) => wanted.includes(norm(c.section)));
    if (hit) return { pass: true, score: 1, reason: `Cited ${doc} § ${hit.section}` };
  }

  const expected = passages
    .map(({ doc, sections }) => (sections && sections.length ? `${doc} § ${sections.join(' | ')}` : doc))
    .join(' OR ');
  return { pass: false, score: 0, reason: `Did not cite the passage used. Expected: ${expected}. Cited: ${cited}` };
};
