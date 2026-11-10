"""Summarize promptfoo output into results.json: pass rate and pass^k per test,
by category, by metric and overall, for each Ask HR version (provider label),
plus a v1 -> v1.1 comparison.

Usage:
    promptfoo eval --repeat 3                       # writes results/promptfoo-latest.json
    python3 scripts/summarize_results.py            # -> results.json

    # several raw files (e.g. v1 and v1.1 run separately):
    python3 scripts/summarize_results.py results/v1.json results/v11.json -o results.json

pass_rate      passing runs / all runs
pass_all       every run of the test passed (pass^k, k = runs per test)
metric pass    a run passes a metric when all its assertions with that metric pass
Errored runs count as failures.

Comparison statuses (on pass_all): fixed, regressed, still_failing, still_passing.
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INPUT = "results/promptfoo-latest.json"
DEFAULT_BASELINE = "ask-hr-v1"
DEFAULT_CANDIDATE = "ask-hr-v1.1"

# Citation precision is advisory: reported per metric, never decides pass/fail.
# A citation is "unrelated" when its article is not in the test's metadata.articles
# (plus general how-to articles). For questions the articles don't answer
# (articles: []), any citation is unrelated.
ALWAYS_RELATED = {"hr-hub-guide"}
ADVISORY_ASSERTION_VALUES = {"file://tests/assertions/no_unrelated_citations.js"}  # older runs


def unrelated_citations(citations, articles):
    if not isinstance(articles, list):
        return None  # test has no article list: not scored
    allowed = set(articles) | ALWAYS_RELATED if articles else set()
    return [f"{c.get('doc_id')} § {c.get('section')}" for c in citations if c.get("doc_id") not in allowed]


# Lumora's v1.1 release notes. Each fix is checked by tests tagged
# `metadata.release_note: <key>`, or by every assertion with a given metric.
RELEASE_NOTES = {
    "remote_state_policies": {"claim": "Remote employees get their own state's policies.", "tag": "remote_state_policies"},
    "citations_point_at_passage": {"claim": "Citations point at the passage the answer used.", "metric": "citation"},
    "managers_own_team": {"claim": "Managers see only their own team.", "tag": "managers_own_team"},
    "employee_time_zone": {"claim": "Dates use the employee's time zone.", "tag": "employee_time_zone"},
}


def load_runs(paths):
    runs = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        for r in data["results"]["results"]:
            test = r.get("testCase") or {}
            meta = test.get("metadata") or {}
            components = [
                c
                for c in (r.get("gradingResult") or {}).get("componentResults", [])
                if c.get("assertion", {}).get("value") not in ADVISORY_ASSERTION_VALUES
            ]
            response = r.get("response") or {}
            unrelated = unrelated_citations((response.get("metadata") or {}).get("citations") or [], meta.get("articles"))
            metrics = defaultdict(lambda: True)
            for c in components:
                m = c.get("assertion", {}).get("metric") or "unnamed"
                metrics[m] = metrics[m] and bool(c.get("pass"))
            if unrelated is not None:
                metrics["citation_precision (advisory)"] = not unrelated
            errored = not r.get("gradingResult")
            gated = [c for c in components if c.get("assertion", {}).get("metric") != "citation_precision (advisory)"]
            runs.append(
                {
                    "version": (r.get("provider") or {}).get("label") or (r.get("provider") or {}).get("id"),
                    "test": test.get("description") or f"test {r.get('testIdx')}",
                    "category": meta.get("category", "uncategorized"),
                    "release_note": meta.get("release_note"),
                    "employee_id": (r.get("vars") or {}).get("employee_id"),
                    # Recomputed without advisory checks: errors fail, otherwise all assertions must pass
                    "pass": (not errored) and all(c.get("pass") for c in gated),
                    "unrelated_citations": unrelated or [],
                    "metrics": dict(metrics),
                    "error": r.get("error") if errored else None,
                    "failed_assertions": [
                        {
                            "metric": c.get("assertion", {}).get("metric"),
                            "type": c.get("assertion", {}).get("type"),
                            "reason": (c.get("reason") or "")[:300],
                        }
                        for c in components
                        if not c.get("pass")
                    ],
                    "output": ((r.get("response") or {}).get("output") or "")[:500],
                }
            )
    return runs


def rate(n, d):
    return round(n / d, 4) if d else None


def block(tests):
    total_runs = sum(t["runs"] for t in tests)
    return {
        "tests": len(tests),
        "runs": total_runs,
        "pass_rate": rate(sum(t["passes"] for t in tests), total_runs),
        "pass_all_rate": rate(sum(t["pass_all"] for t in tests), len(tests)),
    }


def summarize_version(tests):
    per_test = []
    metric_runs = defaultdict(lambda: [0, 0])  # metric -> [passing runs, runs]
    for name, test_runs in tests.items():
        passes = sum(r["pass"] for r in test_runs)
        metrics = {}
        for m in sorted({m for r in test_runs for m in r["metrics"]}):
            relevant = [r for r in test_runs if m in r["metrics"]]
            ok = sum(r["metrics"][m] for r in relevant)
            metrics[m] = {"passes": ok, "runs": len(relevant), "pass_all": ok == len(relevant)}
            metric_runs[m][0] += ok
            metric_runs[m][1] += len(relevant)
        per_test.append(
            {
                "test": name,
                "category": test_runs[0]["category"],
                "release_note": test_runs[0]["release_note"],
                "employee_id": test_runs[0]["employee_id"],
                "runs": len(test_runs),
                "passes": passes,
                "pass_rate": rate(passes, len(test_runs)),
                "pass_all": passes == len(test_runs),
                "metrics": metrics,
                "failures": [
                    {"error": r["error"], "failed_assertions": r["failed_assertions"], "output": r["output"]}
                    for r in test_runs
                    if not r["pass"]
                ],
                "unrelated_citations (advisory)": sorted({c for r in test_runs for c in r["unrelated_citations"]}),

            }
        )

    categories = defaultdict(list)
    for t in per_test:
        categories[t["category"]].append(t)

    return {
        "overall": block(per_test),
        "by_category": {c: block(items) for c, items in sorted(categories.items())},
        "by_metric": {m: {"runs": n, "pass_rate": rate(ok, n)} for m, (ok, n) in sorted(metric_runs.items())},
        "by_test": sorted(per_test, key=lambda t: (t["category"], t["test"])),
    }


def release_note_view(version_summary):
    view = {}
    for key, note in RELEASE_NOTES.items():
        if "tag" in note:
            tests = [t for t in version_summary["by_test"] if t["release_note"] == note["tag"]]
            view[key] = {"claim": note["claim"], "checked_by": f"tests tagged {note['tag']}", **block(tests)}
        else:
            m = note["metric"]
            with_metric = [t for t in version_summary["by_test"] if m in t["metrics"]]
            runs = sum(t["metrics"][m]["runs"] for t in with_metric)
            view[key] = {
                "claim": note["claim"],
                "checked_by": f"every '{m}' assertion",
                "tests": len(with_metric),
                "runs": runs,
                "pass_rate": rate(sum(t["metrics"][m]["passes"] for t in with_metric), runs),
                "pass_all_rate": rate(sum(t["metrics"][m]["pass_all"] for t in with_metric), len(with_metric)),
            }
    return view


def compare(base, cand, base_label, cand_label):
    base_tests = {t["test"]: t for t in base["by_test"]}
    cand_tests = {t["test"]: t for t in cand["by_test"]}
    rows = defaultdict(list)
    for name in sorted(set(base_tests) & set(cand_tests)):
        b, c = base_tests[name], cand_tests[name]
        status = {
            (False, True): "fixed",
            (True, False): "regressed",
            (False, False): "still_failing",
            (True, True): "still_passing",
        }[(b["pass_all"], c["pass_all"])]
        rows[status].append(
            {
                "test": name,
                "category": b["category"],
                "release_note": b["release_note"],
                f"{base_label}_pass_rate": b["pass_rate"],
                f"{cand_label}_pass_rate": c["pass_rate"],
                # What the candidate still gets wrong (first failing run)
                **({"candidate_failure": c["failures"][0]} if c["failures"] else {}),
            }
        )

    def delta(a, b):
        return round(b - a, 4) if a is not None and b is not None else None

    base_rn, cand_rn = release_note_view(base), release_note_view(cand)
    return {
        "baseline": base_label,
        "candidate": cand_label,
        "overall": {
            "pass_rate": [base["overall"]["pass_rate"], cand["overall"]["pass_rate"]],
            "pass_all_rate": [base["overall"]["pass_all_rate"], cand["overall"]["pass_all_rate"]],
            "pass_all_rate_delta": delta(base["overall"]["pass_all_rate"], cand["overall"]["pass_all_rate"]),
        },
        "counts": {k: len(rows.get(k, [])) for k in ("fixed", "regressed", "still_failing", "still_passing")},
        "release_notes": {
            k: {
                "claim": base_rn[k]["claim"],
                "checked_by": base_rn[k]["checked_by"],
                "tests": cand_rn[k]["tests"],
                f"{base_label}_pass_all_rate": base_rn[k]["pass_all_rate"],
                f"{cand_label}_pass_all_rate": cand_rn[k]["pass_all_rate"],
                "verdict": verdict(base_rn[k]["pass_all_rate"], cand_rn[k]["pass_all_rate"]),
            }
            for k in RELEASE_NOTES
        },
        "by_category": {
            c: {
                "pass_all_rate": [base["by_category"].get(c, {}).get("pass_all_rate"), cand["by_category"].get(c, {}).get("pass_all_rate")],
                "delta": delta(base["by_category"].get(c, {}).get("pass_all_rate"), cand["by_category"].get(c, {}).get("pass_all_rate")),
            }
            for c in sorted(set(base["by_category"]) | set(cand["by_category"]))
        },
        "by_metric": {
            m: {
                "pass_rate": [base["by_metric"].get(m, {}).get("pass_rate"), cand["by_metric"].get(m, {}).get("pass_rate")],
                "delta": delta(base["by_metric"].get(m, {}).get("pass_rate"), cand["by_metric"].get(m, {}).get("pass_rate")),
            }
            for m in sorted(set(base["by_metric"]) | set(cand["by_metric"]))
        },
        "tests": {k: rows.get(k, []) for k in ("regressed", "fixed", "still_failing", "still_passing")},
    }


def verdict(before, after):
    if before is None or after is None:
        return "no tests"
    if after == 1:
        return "fixed" if before < 1 else "already passing"
    if after > before:
        return "partly fixed"
    if after < before:
        return "worse"
    return "not fixed"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", default=[DEFAULT_INPUT], help="promptfoo JSON output file(s)")
    ap.add_argument("-o", "--output", default="results.json")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    ap.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    ap.add_argument("--label", help="name for this run, e.g. before-fixes / after-fixes")
    args = ap.parse_args()

    runs = load_runs(args.inputs)
    grouped = defaultdict(lambda: defaultdict(list))
    for run in runs:
        grouped[run["version"]][run["test"]].append(run)

    versions = {v: summarize_version(tests) for v, tests in grouped.items()}
    for v in versions.values():
        v["release_notes"] = release_note_view(v)

    runs_per_test = sorted({len(rs) for tests in grouped.values() for rs in tests.values()})
    result = {
        "label": args.label,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": args.inputs,
        "runs_per_test": runs_per_test[0] if len(runs_per_test) == 1 else runs_per_test,
        "definitions": {
            "pass_rate": "passing runs / total runs",
            "pass_all_rate": "share of tests where every run passed (pass^k)",
            "comparison status": "fixed / regressed / still_failing / still_passing, on pass_all",
            "citation_precision (advisory)": "share of runs citing only related articles; reported, not used for pass/fail",
        },
        "versions": versions,
    }
    if args.baseline in versions and args.candidate in versions:
        result["comparison"] = compare(versions[args.baseline], versions[args.candidate], args.baseline, args.candidate)

    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    for version, v in versions.items():
        o = v["overall"]
        print(f"{version}: {o['tests']} tests, {o['runs']} runs, pass rate {o['pass_rate']:.1%}, pass^k {o['pass_all_rate']:.1%}")
    if "comparison" in result:
        c = result["comparison"]
        print(f"{args.baseline} -> {args.candidate}: " + ", ".join(f"{k} {n}" for k, n in c["counts"].items()))
        for k, rn in c["release_notes"].items():
            print(f"  {rn['claim']:<50} {rn[f'{args.baseline}_pass_all_rate']} -> {rn[f'{args.candidate}_pass_all_rate']}  ({rn['verdict']})")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
