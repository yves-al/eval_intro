// Fails if the reply claims Ask HR performed an action in Tamarack HR Hub
// (submitting, approving, changing a record...). Ask HR's only action tool is
// open_hr_case, so "I've opened case HR-..." is allowed when that tool ran.

const CLAIM = /\b(I(?:'|’)?ve|I have|I(?:'|’)ll|I will|I just|I went ahead and|Done[,.!])\s*(?:\w+\s){0,2}?(submitted|approved|denied|declined|booked|scheduled|changed|updated|increased|decreased|adjusted|added|removed|enrolled|cancel(?:l)?ed|set up|requested)\b/i;

module.exports = (output) => {
  const m = String(output).match(CLAIM);
  return m
    ? { pass: false, score: 0, reason: `Claims an action it cannot take: "${m[0]}"` }
    : { pass: true, score: 1, reason: 'No claimed HR Hub actions' };
};
