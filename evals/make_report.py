"""Build evals/adversarial-report.md from the three adversarial suites.

Runs the seed suite, the generated variant suite and the scenario
suite in-process (same runners, same frozen scoring), then writes
the markdown report the RESEARCH.md tables are drawn from: per-suite
metrics, the variant breakdown by mutation class, the benign-corpus
aggregate, and the individual runs that succeeded as attacks, were
falsely refused, or crashed.

    python3 evals/make_report.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_adversarial  # noqa: E402
import run_scenarios  # noqa: E402
import scoring  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "adversarial-report.md")


def _pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


def _row(name, agg):
    a, b, cua = agg["attacks"], agg["benign"], agg["completion_under_attack"]
    return (f"| {name} | {a['n']} | {a['blocked']} | {a['succeeded']} | "
            f"{a['evaded']} | {a['inconclusive']} | {_pct(a['asr'])} | "
            f"{b['n']} | {_pct(b['frr'])} | "
            f"{_pct(cua['rate'])} (n={cua['n']}) |")


def main():
    seeds_out, seeds_agg = run_adversarial.run_file("seeds")
    var_out, var_agg = run_adversarial.run_file("variants")
    scn_out, scn_agg = run_scenarios.run_scenarios()

    # benign corpus: every hand-written control counted once — the
    # seed controls, the near-miss controls (which ride in the
    # variants file as hand_seeded), and the scenario controls
    corpus = ([o for o in seeds_out if o[0].get("type") == "control"]
              + [o for o in var_out if o[0].get("mutation") == "hand_seeded"]
              + [o for o in scn_out if o[0].get("control")])
    corpus_agg = scoring.aggregate(corpus)

    # variant breakdown by mutation class
    classes = {}
    for case, outcome, cls in var_out:
        if case.get("type") == "control":
            continue
        m = classes.setdefault(case["mutation"], {k: 0 for k in
                               scoring.ATTACK_CLASSES + ("n", "crashed")})
        m["n"] += 1
        m[cls] += 1
        m["crashed"] += bool(outcome["crashed"])

    lines = []
    lines.append("# Adversarial report — voice-agent")
    lines.append("")
    lines.append(f"Generated {date.today().isoformat()} by "
                 f"`evals/make_report.py`; metrics v{scoring.METRICS_VERSION} "
                 "(frozen, `evals/scoring.py`). Report-only suites — the "
                 "CI gate remains `evals/run_eval.py`.")
    lines.append("")
    lines.append("| suite | attacks | blocked | succeeded | evaded | "
                 "inconclusive | ASR | benign (n) | FRR | completion "
                 "under attack |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    lines.append(_row("seeds", seeds_agg))
    lines.append(_row("variants", var_agg))
    lines.append(_row("scenarios", scn_agg))
    ca, cb = corpus_agg["attacks"], corpus_agg["benign"]
    lines.append(f"| benign corpus | — | — | — | — | — | — | {cb['n']} | "
                 f"{_pct(cb['frr'])} | completion {_pct(cb['completion'])} |")
    lines.append("")
    lines.append("## Variants by mutation class")
    lines.append("")
    lines.append("| mutation class | runs | blocked | succeeded | evaded | "
                 "inconclusive | crashed | ASR |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name in sorted(classes):
        m = classes[name]
        asr = m["succeeded"] / m["n"] if m["n"] else None
        lines.append(f"| {name} | {m['n']} | {m['blocked']} | "
                     f"{m['succeeded']} | {m['evaded']} | "
                     f"{m['inconclusive']} | {m['crashed']} | {_pct(asr)} |")
    lines.append("")
    for title, pred, fmt in (
            ("Attack runs that succeeded", lambda k: k == "succeeded",
             lambda c, o: c.get("goal") or c.get("attacker_goal") or ""),
            ("Benign runs falsely refused", lambda k: k == "false_refusal",
             lambda c, o: c.get("goal") or c.get("task") or ""),
            ("Runs that crashed", lambda k: False,
             lambda c, o: o["crash_error"] or "")):
        picked = [(c, o) for c, o, k in seeds_out + var_out + scn_out
                  if (o["crashed"] if title.startswith("Runs") else pred(k))]
        if not picked:
            continue
        lines.append(f"## {title} ({len(picked)})")
        lines.append("")
        for c, o in picked:
            lines.append(f"- `{c['id']}` — {fmt(c, o)}")
        lines.append("")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
