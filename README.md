# voice-agent

## Release notes — v1.0 (2026-10-20)

Measured numbers, offline, mock brain — every figure below comes from
`python3 evals/run_eval.py`, re-run today.

- **Task completion: 7/7 scripted calls** — booking (happy path), booking
  declined at confirm, two order-status checks, opening hours, mid-flow
  bail-out, and a bad order number handled gracefully. Scenarios are
  graded on **end state in the business store** (a booking actually
  exists, or doesn't), not on reply text — see `docs/adr/0003`.
- **Turn latency: 0.0 ms average, 19/19 turns within the 800 ms budget**
  — backend decision latency only. Honest scope: speech recognition and
  synthesis run in the browser and aren't timed here; the budget exists
  so a real LLM brain (one network call per turn) is measured against
  the same bar a phone call demands.

A voice receptionist you can talk to in your browser — no key, no cost.

## Live demo

**[https://tushar29k-voice-agent.onrender.com](https://tushar29k-voice-agent.onrender.com)** — Click the mic and talk to the BrightSmile Dental receptionist: book an appointment, check an order, ask the hours. Watch each turn's latency and function calls in the trace.
> Hosted on Render's free tier — the first visit after a while can take ~30s while the instance wakes up. Speech input needs Chrome or Edge; typed turns work everywhere.

## The idea

Most "voice AI" demos hide the conversation behind the speech demo.
This one inverts it: speech is the commodity layer (the browser's Web
Speech API — see `docs/adr/0002`), and the project is the part that
actually breaks in production:

- **Latency discipline** — every turn is timed against an 800 ms
  backend budget, printed in the UI and asserted in the evals.
- **Slot filling as a state machine** (`agent.py`) — day → time → name →
  explicit confirm before anything is booked. Voice can't afford an
  LLM meandering mid-turn; the machine is explicit, interruptible
  ("cancel that" bails out cleanly) and evaluable.
- **Function calling into a real (mock) business system**
  (`business_api.py`) — appointments with real slot state (a taken slot
  is taken), orders with real statuses. The agent's "you're booked" is
  only true because the store says so.
- **Conversation trace** — every turn logs intent, tool calls with their
  own timings, reply, and latency, visible in the UI and via
  `GET /session/<id>`.

## Architecture

```
browser                          server
┌──────────────────┐   text    ┌───────────────────┐
│ Web Speech ASR   │ ────────▶ │ VoiceAgent (agent)│
│ (mic → text)     │           │  intent detect +  │
│                  │           │  slot state mach. │
│ Web Speech TTS   │ ◀──────── │        │          │
│ (text → voice)   │   reply   │        ▼ tool calls│
└──────────────────┘           │ business_api      │
                               │  slots · orders   │
                               └───────────────────┘
  each turn measured against an 800 ms backend budget
```

## API

```
POST /turn            {"session_id": "s1", "text": "..."}
                      -> {reply, intent, tool_calls[], latency_ms, budget_ok}
GET  /session/<id>    the whole conversation, for inspection
GET  /bookings        current slot book + orders (the side effects)
GET  /info            backend honesty badge
```

## Evals

```
python3 evals/run_eval.py
```

7 scripted calls. Pass = the business store is in the expected end
state. Latency and budget adherence are reported per run and recorded
in `evals/eval-history.jsonl`.
