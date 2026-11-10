"""Export a sample of LLM-judge verdicts for hand labeling.

Picks llm-rubric judgments from a promptfoo results file, balanced between
replies the judge passed and failed, at most one per (test, version).
Fill in `human_verdict` (pass / fail) in the CSV, then run judge_agreement.py.

Usage:
    python3 scripts/judge_sample.py results/raw-after-fixes.json -n 40 -o judge/judge_labels.csv
"""

import argparse
import csv
import json
import random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="results/raw-after-fixes.json")
    ap.add_argument("-n", type=int, default=40, help="sample size (half judge-pass, half judge-fail when possible)")
    ap.add_argument("-o", "--output", default="judge/judge_labels.csv")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text())
    seen, judged = set(), []
    for r in data["results"]["results"]:
        version = (r.get("provider") or {}).get("label")
        test = (r.get("testCase") or {}).get("description")
        for c in (r.get("gradingResult") or {}).get("componentResults", []):
            a = c.get("assertion") or {}
            if a.get("type") != "llm-rubric":
                continue
            vars_ = r.get("vars") or {}
            turns = json.loads(vars_["turns"]) if vars_.get("turns") else []
            judged.append(
                {
                    "key": (test, version, " ".join(str(a.get("value")).split())[:80]),
                    "version": version,
                    "test": test,
                    "employee_id": vars_.get("employee_id"),
                    "conversation": " || ".join(turns + [vars_.get("question", "")]),
                    "reply": ((r.get("response") or {}).get("output") or "").strip(),
                    "criterion": " ".join(str(a.get("value")).split()),
                    "judge_verdict": "pass" if c.get("pass") else "fail",
                    "judge_reason": " ".join((c.get("reason") or "").split()),
                }
            )

    rng = random.Random(args.seed)
    rng.shuffle(judged)
    picked = {"pass": [], "fail": []}
    for j in judged:
        if (j["test"], j["version"]) in seen:
            continue
        bucket = picked[j["judge_verdict"]]
        if len(bucket) < args.n // 2:
            bucket.append(j)
            seen.add((j["test"], j["version"]))
    sample = picked["fail"] + picked["pass"]
    # Top up from whichever side has more if one side ran short
    for j in judged:
        if len(sample) >= args.n:
            break
        if (j["test"], j["version"]) not in seen:
            sample.append(j)
            seen.add((j["test"], j["version"]))
    rng.shuffle(sample)  # don't label in judge order

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "version", "test", "employee_id", "conversation", "reply", "criterion",
            "human_verdict", "human_notes", "judge_verdict", "judge_reason"]
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for i, j in enumerate(sample, 1):
            w.writerow({"id": i, "human_verdict": "", "human_notes": "", **j})
    fails = sum(j["judge_verdict"] == "fail" for j in sample)
    print(f"Wrote {len(sample)} judgments ({fails} judge-fail, {len(sample) - fails} judge-pass) to {args.output}")
    print("Label human_verdict as pass/fail BEFORE reading judge_verdict / judge_reason (last two columns).")


if __name__ == "__main__":
    main()
