# ADR 0002 — speech lives in the browser, the brain lives server-side

## Decision

Recognition and synthesis use the browser's Web Speech API. The server
receives and returns text only, over `POST /turn`.

## Why

Server-side ASR/TTS means audio streaming, codec plumbing and a paid
speech API before the interesting part — the conversation — even
starts. Keeping audio at the client keeps the demo free, the backend
text-testable, and the latency budget honest: we measure backend
decision latency, the part we control. The README states this split
openly rather than implying we built a speech stack.

## Cost

Speech quality, accents and browser support are whatever the client's
browser gives us (Chrome is good; some browsers have no recognition at
all — the UI falls back to typed turns, fully featured). For a real
clinic deployment, this layer is the swap point for a telephony-grade
ASR/TTS provider.
