// Fails if Ask HR opened an HR case in a test that does not expect one.
// Tests that should open a case set `metadata.allow_case: true`; their own
// assertions then check the category and priority.

module.exports = (output, context) => {
  if (context.test?.metadata?.allow_case) {
    return { pass: true, score: 1, reason: 'Test allows an HR case' };
  }
  const cases = context.metadata?.cases || [];
  return cases.length
    ? {
        pass: false,
        score: 0,
        reason: `Opened an HR case nobody asked for: ${cases.map((c) => `${c.case_id} ${c.category}/${c.priority}`).join(', ')}`,
      }
    : { pass: true, score: 1, reason: 'No HR case opened' };
};
