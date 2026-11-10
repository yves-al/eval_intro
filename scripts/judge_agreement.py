"""Measure how well the LLM judge agrees with hand labels.

"The reply fails" is the positive class (README definitions):
  precision = of replies the judge failed, the share you also failed
  recall    = of replies you failed, the share the judge also failed

Usage:
    python3 scripts/judge_agreement.py judge/judge_labels.csv -o JUDGE_VALIDATION.md
"""

import argparse
import csv
from pathlib import Path


def norm(v):
    v = (v or "").strip().lower()
    return {"pass": "pass", "p": "pass", "y": "pass", "yes": "pass", "fail": "fail", "f": "fail", "n": "fail", "no": "fail"}.get(v)


def pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="judge/judge_labels.csv")
    ap.add_argument("-o", "--output", default="JUDGE_VALIDATION.md")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input)))
    labeled = [r for r in rows if norm(r["human_verdict"])]
    if not labeled:
        raise SystemExit(f"No human_verdict filled in {args.input}. Label rows as pass/fail first.")

    tp = sum(norm(r["judge_verdict"]) == "fail" and norm(r["human_verdict"]) == "fail" for r in labeled)
    fp = sum(norm(r["judge_verdict"]) == "fail" and norm(r["human_verdict"]) == "pass" for r in labeled)
    fn = sum(norm(r["judge_verdict"]) == "pass" and norm(r["human_verdict"]) == "fail" for r in labeled)
    tn = sum(norm(r["judge_verdict"]) == "pass" and norm(r["human_verdict"]) == "pass" for r in labeled)
    n = len(labeled)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    agreement = (tp + tn) / n
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((fn + tn) / n) * ((fp + tn) / n)
    kappa = (agreement - (p_yes + p_no)) / (1 - (p_yes + p_no)) if (p_yes + p_no) < 1 else None

    disagreements = [r for r in labeled if norm(r["judge_verdict"]) != norm(r["human_verdict"])]
    lines = [
        "# LLM judge validation",
        "",
        f"Hand-labeled {n} of {len(rows)} sampled judgments from `{args.input}` "
        "(sampled by `scripts/judge_sample.py`, balanced between judge-pass and judge-fail, "
        "labeled without looking at the judge's verdict). Positive class: the reply fails.",
        "",
        "| | Human: fail | Human: pass |",
        "| --- | --- | --- |",
        f"| **Judge: fail** | {tp} (TP) | {fp} (FP) |",
        f"| **Judge: pass** | {fn} (FN) | {tn} (TN) |",
        "",
        f"- **Precision:** {pct(precision)}: of the replies the judge failed, the share I also failed.",
        f"- **Recall:** {pct(recall)}: of the replies I failed, the share the judge also failed.",
        f"- **Agreement:** {pct(agreement)}; Cohen's kappa {kappa:.2f}." if kappa is not None else f"- **Agreement:** {pct(agreement)}.",
        "",
        "Because the sample is balanced (not proportional to how often the judge passes), "
        "precision here is not the precision on the full suite; recall and the per-case "
        "disagreements are the useful signals.",
        "",
        "## Disagreements",
        "",
    ]
    if not disagreements:
        lines.append("None.")
    for r in disagreements:
        lines += [
            f"### #{r['id']} {r['test']} ({r['version']})",
            "",
            f"- **Judge:** {r['judge_verdict']}, **me:** {norm(r['human_verdict'])}",
            f"- **Criterion:** {r['criterion']}",
            f"- **Reply:** {r['reply']}",
            f"- **Judge's reason:** {r['judge_reason']}",
            f"- **My note:** {r['human_notes'] or '-'}",
            "",
        ]
    Path(args.output).write_text("\n".join(lines))
    print(f"precision {pct(precision)}, recall {pct(recall)}, agreement {pct(agreement)} on {n} labels -> {args.output}")


if __name__ == "__main__":
    main()
