"""Voice-agent evals: scripted conversations, run headlessly (offline).

Each scenario is a list of user turns plus an expectation about the END
STATE (not just the reply text): a booking must exist in the store, an
order status must have been answered. That's the voice-agent equivalent
of groundedness — "said it" vs "did it".

Also measured: per-turn backend latency against the 800 ms budget
(speech recognition/synthesis happens in the browser and is excluded —
stated openly in the README).

Run: python3 evals/run_eval.py
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import business_api as api  # noqa: E402
from agent import VoiceAgent  # noqa: E402

SCENARIOS = [
    {"name": "book happy path",
     "turns": ["hi", "I want to book an appointment", "tomorrow",
               "afternoon", "this is Ravi Kumar", "yes"],
     "expect": {"booked_for": "Ravi Kumar"}},
    {"name": "book then decline confirm",
     "turns": ["book please", "friday", "morning", "I'm Meera", "no"],
     "expect": {"no_booking": True}},
    {"name": "check order 1001",
     "turns": ["where is my order 1001"],
     "expect": {"reply_contains": "shipped"}},
    {"name": "check order 1002 after greeting",
     "turns": ["hello", "can you check my order?", "order 1002"],
     "expect": {"reply_contains": "in preparation"}},
    {"name": "ask hours",
     "turns": ["what are your opening hours"],
     "expect": {"reply_contains": "9 am to 7 pm"}},
    {"name": "bail out mid-flow",
     "turns": ["book an appointment", "cancel that"],
     "expect": {"reply_contains": "dropped"}},
    {"name": "bad order number handled",
     "turns": ["check order 9999"],
     "expect": {"reply_contains": "couldn't find"}},
]


def check(expect, agent, sess_id, last_reply):
    if "booked_for" in expect:
        return any(s["taken"] and s["patient"] == expect["booked_for"]
                   for s in api.SLOTS)
    if "no_booking" in expect:
        return not any(s["taken"] for s in api.SLOTS)
    if "reply_contains" in expect:
        return expect["reply_contains"] in last_reply
    return False


def main():
    passed, latencies, budget_ok = 0, [], 0
    for sc in SCENARIOS:
        # fresh business state per scenario so bookings don't collide
        api.SLOTS[:] = api._slots()
        agent = VoiceAgent()
        agent.sessions.clear()
        sid = f"eval-{sc['name']}"
        last = ""
        for text in sc["turns"]:
            rec = agent.turn(sid, text)
            last = rec["reply"]
            latencies.append(rec["latency_ms"])
            budget_ok += rec["budget_ok"]
        ok = check(sc["expect"], agent, sid, last)
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {sc['name']}")
    total_turns = len(latencies)
    print(f"task completion: {passed}/{len(SCENARIOS)} scenarios")
    print(f"turn latency: avg {statistics.mean(latencies):.1f} ms, "
          f"p95 {sorted(latencies)[int(0.95 * (len(latencies) - 1))]:.1f} ms "
          f"(backend only)")
    print(f"budget: {budget_ok}/{total_turns} turns within 800 ms")
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "eval-history.jsonl"), "a") as f:
        f.write(json.dumps({"completed": passed, "total": len(SCENARIOS),
                            "avg_turn_ms": round(statistics.mean(latencies), 1),
                            "budget_ok": budget_ok, "turns": total_turns}) + "\n")
    return 0 if passed == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(main())
