"""Run an adversarial suite file (seeds or variants) and score it.

    python3 evals/run_adversarial.py            # adversarial.yaml (seeds)
    python3 evals/run_adversarial.py variants   # adversarial_variants.yaml

Report-only by design: this suite never gates CI (the gate is
run_eval.py). Every run prints one line per case with its frozen
outcome class (scoring.py), a summary, and appends a line to
eval-history.jsonl — the numbers steer the fix phase, they don't
block commits.
"""
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import scoring  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"seeds": "adversarial.yaml", "variants": "adversarial_variants.yaml"}


def run_file(name):
    data = yaml.safe_load(open(os.path.join(HERE, FILES[name])))
    outcomes = []
    for case in data["cases"]:
        outcome = harness.run_case(case, sid_prefix=name)
        cls = scoring.classify(case, outcome)
        outcomes.append((case, outcome, cls))
        flag = " CRASHED" if outcome["crashed"] else ""
        print(f"{cls:14s} {case['id']}{flag}")
    agg = scoring.aggregate(outcomes)
    a, b = agg["attacks"], agg["benign"]
    print(f"\n{name}: attacks n={a['n']} blocked={a['blocked']} "
          f"succeeded={a['succeeded']} evaded={a['evaded']} "
          f"inconclusive={a['inconclusive']} "
          f"ASR={_pct(a['asr'])}")
    print(f"{name}: benign n={b['n']} completed={b['completed']} "
          f"false_refusal={b['false_refusal']} "
          f"inconclusive={b['inconclusive']} FRR={_pct(b['frr'])}")
    with open(os.path.join(HERE, "eval-history.jsonl"), "a") as f:
        f.write(json.dumps({"suite": f"adversarial-{name}",
                            "metrics_version": scoring.METRICS_VERSION,
                            "attacks": a, "benign": b}) + "\n")
    return outcomes, agg


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


if __name__ == "__main__":
    run_file(sys.argv[1] if len(sys.argv) > 1 else "seeds")
