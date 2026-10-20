# ADR 0003 — evals check end state, not transcripts

## Decision

Scenarios pass or fail on the BUSINESS STORE (a booking exists for the
right patient; no booking exists after a declined confirm), not on
whether the agent's reply text "sounds right".

## Why

Reply-text assertions are brittle and reward parroting. The failure
that matters in production is "the agent said you're booked" while
nothing was booked — a text check passes that bug, a state check
catches it. Same principle as support-agent's groundedness: verify the
side effect, not the sentence.

## Cost

Scenarios must reset the store between runs (in-memory store makes
this trivial) and end-state checks can't judge tone — accepted, tone
is a second-order problem next to "did it actually book".
