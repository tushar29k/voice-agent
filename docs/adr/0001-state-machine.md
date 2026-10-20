# ADR 0001 — an explicit state machine, not an LLM in the loop

## Decision

The conversation is driven by a small explicit state machine
(`idle → need_day → need_time → need_name → confirm → idle`) with
regex intent detection. An LLM, when plugged in, may reword replies —
it does not decide state transitions.

## Why

Voice turns have a hard latency budget (800 ms here) and zero tolerance
for wandering: a user on a call who says "tomorrow" needs the next
question, not a creative interpretation. A state machine is also
evaluable — 7 scripted scenarios can prove the booking lands in the
slot book. An LLM-driven slot-filler would need a judge model to grade
every call, which is a cost and latency tax on the thing being graded.

## Cost

New intents mean new patterns and states, by hand. Accepted: a dental
receptionist has maybe a dozen intents worth automating; the rest
should escalate to a human anyway.
