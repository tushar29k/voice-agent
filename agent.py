"""The conversational agent: intent detection, slot filling, tool calls.

Spoken-turn scope: this module is text in / text out. Speech recognition
and synthesis live in the browser (Web Speech API) — the backend never
pretends to do audio. What it does is the hard part of a voice agent:
hold a multi-turn slot-filling conversation, call tools, and answer
within a per-turn latency budget.

Design:
- a tiny explicit state machine per session (idle -> collecting date ->
  collecting time -> confirming -> done), not an LLM free-for-all —
  voice calls can't afford a model meandering mid-turn (docs/adr/0001)
- the mock brain decides intent and words replies; a real model can
  replace the wording only (same seam as support-agent)
- every turn records: intent, tool calls, reply, latency_ms, budget_ok
"""
import os
import re
import time

import business_api as api

BUDGET_MS = 800  # backend turn budget — under this feels instant on voice

SESSIONS = {}

_INTENT_PATTERNS = [
    ("book", re.compile(r"\b(book|appointment|schedule|see the doctor|visit)\b", re.I)),
    ("order", re.compile(r"\border\s*(?:status)?\b|where.{0,10}my (order|package)", re.I)),
    ("hours", re.compile(r"\b(open|hours|timing|when.*(open|close))\b", re.I)),
    ("greet", re.compile(r"^(hi|hello|hey)\b", re.I)),
    ("bye", re.compile(r"\b(bye|goodbye|thanks?|thank you)\b", re.I)),
    ("cancel", re.compile(r"\bcancel\b", re.I)),
]

_DAYS = re.compile(r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
_TIME = re.compile(r"\b(morning|afternoon|10(?:[:.]00)?(?: ?am)?|2(?:[:.]30)?(?: ?pm)?|14(?::30)?)\b", re.I)
_ORDER_ID = re.compile(r"\b(?:order\s*#?\s*)?(\d{4})\b", re.I)
_NAME = re.compile(r"\b(?:this is|i am|i'm|name is)\s+([a-z][a-z ]{1,30})\b", re.I)


def _detect_intent(text):
    for name, pat in _INTENT_PATTERNS:
        if pat.search(text):
            return name
    return "unknown"


def _spelled_out(words):
    return " ".join(words)  # hook: "t o m o r r o w" -> "tomorrow"


class VoiceAgent:
    def __init__(self):
        self.sessions = SESSIONS

    def _session(self, sid):
        return self.sessions.setdefault(sid, {"state": "idle", "slots": {},
                                               "turns": []})

    def turn(self, session_id, text):
        """One user turn -> dict with reply, tool_calls, trace, latency."""
        t0 = time.perf_counter()
        sess = self._session(session_id)
        tool_calls = []
        intent = _detect_intent(text)

        def call_tool(name, **kw):
            # one log line per call, with its own timing
            t = time.perf_counter()
            fn = getattr(api, name)
            res = fn(**kw)
            dt = (time.perf_counter() - t) * 1000
            tool_calls.append({"tool": name, "args": kw,
                               "ms": round(dt, 1), "result": res})
            return res

        reply = self._handle(sess, intent, text, call_tool)
        latency = (time.perf_counter() - t0) * 1000
        turn_rec = {"intent": intent, "user": text, "reply": reply,
                    "tool_calls": tool_calls, "latency_ms": round(latency, 1),
                    "budget_ok": latency <= BUDGET_MS}
        sess["turns"].append(turn_rec)
        return turn_rec

    # -- the state machine ------------------------------------------------
    def _handle(self, sess, intent, text, call_tool):
        st = sess["state"]
        if intent == "bye":
            sess["state"] = "idle"
            return "Goodbye! Take care, and call us back if you need anything."
        if intent == "greet" and st == "idle":
            return ("Hello! You're through to BrightSmile Dental. I can book "
                    "appointments, check order status, or tell you our hours. "
                    "What can I do for you?")
        if intent == "hours":
            r = call_tool("clinic_hours")
            return f"We're open {r['hours']}."
        if intent == "order":
            m = _ORDER_ID.search(text)
            if not m:
                return ("Sure, I can check that. What's the order number? "
                        "It's the four-digit number in your confirmation email.")
            r = call_tool("check_order", order_id=m.group(1))
            if not r["ok"]:
                return ("I couldn't find that order number. Could you read "
                        "it back to me?")
            return (f"Order {m.group(1)}, your {r['item']}, is "
                    f"{r['status']}. It arrives {r['eta']}.")
        if intent == "cancel":
            sess["state"] = "idle"
            return ("No problem, I've dropped what we were doing. Anything "
                    "else?")
        # booking flow: explicit slots, explicit confirm
        if st == "idle" and intent == "book":
            sess["state"] = "need_day"
            return "Of course. Which day works for you? We're open Monday to Saturday."
        if st == "need_day":
            m = _DAYS.search(text)
            day = api.resolve_day(m.group(1).lower()) if m else None
            if not day:
                return "I didn't catch the day. Could you say it again — for example, 'tomorrow' or 'Friday'?"
            sess["slots"]["day"] = day
            sess["state"] = "need_time"
            return (f"Got it, {day}. Morning around 10, or afternoon at "
                    "half past 2?")
        if st == "need_time":
            m = _TIME.search(text)
            time_ = None
            if m:
                w = m.group(1).lower().replace(".", "").replace(":", "")
                if "morning" in w or w.startswith("10"):
                    time_ = "10:00"
                elif "afternoon" in w or w.startswith("2") or w.startswith("14"):
                    time_ = "14:30"
            if not time_:
                return "Morning at 10, or afternoon at half past 2 — which one?"
            sess["slots"]["time"] = time_
            sess["state"] = "need_name"
            return (f"{sess['slots']['day']} at {time_}. And who is the "
                    "appointment for?")
        if st == "need_name":
            m = _NAME.search(text)
            name = m.group(1).strip() if m else text.strip()[:30]
            sess["slots"]["name"] = name
            d, t = sess["slots"]["day"], sess["slots"]["time"]
            sess["state"] = "confirm"
            return (f"So that's {d} at {t} for {name}. Shall I go ahead "
                    "and book it?")
        if st == "confirm":
            if re.search(r"\b(yes|yeah|yep|correct|go ahead|book it)\b", text, re.I):
                r = call_tool("book_appointment", day=sess["slots"]["day"],
                              time=sess["slots"]["time"],
                              patient=sess["slots"].get("name",
                                                      "walk-in caller"))
                sess["state"] = "idle"
                sess["slots"] = {}
                if r["ok"]:
                    b = r["booking"]
                    return (f"Done! You're booked for {b['date']} at "
                            f"{b['time']}. See you then.")
                return ("Ah — that slot just got taken. Want to try a "
                        "different time?")
            if re.search(r"\b(no|not|change)\b", text, re.I):
                sess["state"] = "idle"
                sess["slots"] = {}
                return "Okay, I haven't booked anything. Start over whenever you're ready."
            return ("Sorry — was that a yes to book it, or should I start "
                    "over?")
        # mid-flow smalltalk: hold the state, stay helpful
        return ("I didn't quite catch that. "
                + {"need_day": "Which day works for you?",
                   "need_time": "Morning at 10, or afternoon at half past 2?",
                   "need_name": "Who is the appointment for?",
                   "confirm": "Shall I book it — yes or no?"}[st])
