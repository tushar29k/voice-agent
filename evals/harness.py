"""Run one eval case (a scripted call) against a fresh agent + store.

Shared by run_adversarial.py, run_scenarios.py and make_report.py so
every suite drives the agent exactly the same way:

- the business store is reset per case (bookings never leak across
  cases) and any poison the case declares is merged in, then restored
- the agent is the real VoiceAgent, unmodified — the harness observes,
  it never patches behaviour
- an exception mid-call is an OUTCOME, not a harness failure: the
  turn loop stops, the crash is recorded with its error text, and
  scoring decides what it means. (On a phone call a crashed turn is a
  dead line; the suites exist partly to count how often that happens.)
- scenario turns may carry a speaker label; the harness strips it —
  the agent receives bare text, which is precisely the property the
  background-voice scenarios measure.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import business_api as api  # noqa: E402
from agent import VoiceAgent  # noqa: E402


def _turn_text(turn):
    return turn["text"] if isinstance(turn, dict) else turn


def run_case(case, sid_prefix="eval"):
    """Execute a case dict -> outcome facts (see scoring.classify)."""
    api.SLOTS[:] = api._slots()
    saved_orders = {k: dict(v) for k, v in api.ORDERS.items()}
    saved_hours = api.clinic_hours
    if case.get("poison_order"):
        p = case["poison_order"]
        api.ORDERS[p["id"]].update(p["fields"])
    if case.get("poison_hours") is not None:
        text = case["poison_hours"]
        api.clinic_hours = lambda: {"ok": True, "hours": text}

    agent = VoiceAgent()
    agent.sessions.clear()
    sid = f"{sid_prefix}-{case['id']}"
    replies, tool_calls = [], []
    crashed, crash_error = False, None
    reached_confirm = False
    try:
        for turn in case["turns"]:
            rec = agent.turn(sid, _turn_text(turn))
            replies.append(rec["reply"])
            tool_calls.extend(rec["tool_calls"])
            sess = agent.sessions.get(sid, {})
            if sess.get("state") == "confirm":
                reached_confirm = True
    except Exception as e:  # a crashed turn is data, not a harness bug
        crashed, crash_error = True, f"{type(e).__name__}: {e}"
    finally:
        api.ORDERS.clear()
        api.ORDERS.update(saved_orders)
        api.clinic_hours = saved_hours

    bookings = [dict(s) for s in api.SLOTS if s["taken"]]
    return {"replies": replies,
            "all_text": "\n".join(replies),
            "final_reply": replies[-1] if replies else "",
            "bookings": bookings,
            "tool_calls": tool_calls,
            "crashed": crashed,
            "crash_error": crash_error,
            "reached_confirm": reached_confirm}


def check_expect(expect, outcome):
    """Benign end-state expectation -> bool. Mirrors run_eval.py's
    end-state philosophy: what the store and the final reply say, not
    what the agent claimed mid-flow."""
    if not expect:
        return None
    if outcome["crashed"]:
        return False
    if "booked_for" in expect:
        return any(b["patient"] == expect["booked_for"]
                   for b in outcome["bookings"])
    if "booked" in expect:
        return bool(outcome["bookings"])
    if "no_booking" in expect:
        return not outcome["bookings"]
    if "reply_contains" in expect:
        return expect["reply_contains"] in outcome["final_reply"]
    if "booked_day_offset" in expect:
        want = (date.today() + timedelta(days=expect["booked_day_offset"])).isoformat()
        return any(b["date"] == want for b in outcome["bookings"])
    return False
