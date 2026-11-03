"""Run the AgentDojo-style scenario suite and score it.

    python3 evals/run_scenarios.py

Each scenario is a benign multi-turn call with an attacker payload in
one of the channels a voice agent has (another voice in the room,
poisoned business data, a replayed voicemail). Utility and security
are scored separately by scoring.py: a scenario can succeed as an
attack AND complete as a task, and the report shows both. Report-only
— the gate stays run_eval.py. Appends to eval-history.jsonl.
"""
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import scoring  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def run_scenarios():
    data = yaml.safe_load(open(os.path.join(HERE, "scenarios.yaml")))
    outcomes = []
    for case in data["scenarios"]:
        outcome = harness.run_case(case, sid_prefix="scn")
        cls = scoring.classify(case, outcome)
        outcomes.append((case, outcome, cls))
        flag = " CRASHED" if outcome["crashed"] else ""
        print(f"{cls:14s} {case['id']}{flag}")
    agg = scoring.aggregate(outcomes)
    a, b, cua = agg["attacks"], agg["benign"], agg["completion_under_attack"]
    print(f"\nscenarios: attacks n={a['n']} succeeded={a['succeeded']} "
          f"ASR={_pct(a['asr'])}; benign n={b['n']} "
          f"FRR={_pct(b['frr'])}; completion under "
          f"attack {cua['ok']}/{cua['n']}")
    with open(os.path.join(HERE, "eval-history.jsonl"), "a") as f:
        f.write(json.dumps({"suite": "scenarios",
                            "metrics_version": scoring.METRICS_VERSION,
                            "attacks": a, "benign": b,
                            "completion_under_attack": cua}) + "\n")
    return outcomes, agg


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


if __name__ == "__main__":
    run_scenarios()
