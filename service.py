"""Thin HTTP wrapper around the voice agent.

Speech lives in the browser (Web Speech API for ASR + TTS), the brain
lives here:

  POST /turn     {session_id, text} -> reply + tool calls + latency + trace
  GET  /session/<id>   full conversation so far
  GET  /bookings        current appointment book (side effects, checkable)
  GET  /health, /info
"""
import os as _os

from fastapi import FastAPI
from fastapi.responses import FileResponse as _FileResponse

import business_api as biz
from agent import VoiceAgent

agent = VoiceAgent()
app = FastAPI(title="voice-agent")


@app.post("/turn")
def turn(body: dict):
    rec = agent.turn(body["session_id"], body["text"])
    return {"session_id": body["session_id"], **rec}


@app.get("/session/{session_id}")
def session(session_id: str):
    return {"session_id": session_id,
            "turns": agent.sessions.get(session_id, {}).get("turns", [])}


@app.get("/bookings")
def bookings():
    return {"slots": biz.SLOTS, "orders": biz.ORDERS}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    return {"real_llm": False, "backend": "MockStateMachine",
            "note": "speech in/out is the browser's Web Speech API; "
                    "the brain decides intent and tool calls"}
_UI_INDEX = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "ui", "index.html")


@app.get("/", include_in_schema=False)
def _demo_ui():
    return _FileResponse(_UI_INDEX)
