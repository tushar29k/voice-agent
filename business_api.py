"""Mock business API the voice agent calls — a dental clinic's systems.

Deliberately boring and deterministic: appointments with real slot state,
orders with real statuses. The agent's function calls land here, and the
evals verify the end state in this store — "the agent said it booked"
is not the same as "it booked".
"""
from datetime import date, timedelta

# next 7 days of bookable slots, two times per day
def _slots():
    out = []
    today = date.today()
    for i in range(1, 8):
        d = today + timedelta(days=i)
        for t in ("10:00", "14:30"):
            out.append({"date": d.isoformat(), "time": t, "taken": False,
                        "patient": None})
    return out


SLOTS = _slots()

ORDERS = {
    "1001": {"status": "shipped", "eta": "tomorrow", "item": "whitening kit"},
    "1002": {"status": "in preparation", "eta": "in 3 days", "item": "retainer case"},
    "1003": {"status": "delivered", "eta": "delivered yesterday", "item": "electric toothbrush"},
}


def list_slots():
    return [s for s in SLOTS if not s["taken"]]


def book_appointment(day, time, patient):
    """Book a slot. Returns the booking or an error dict."""
    for s in SLOTS:
        if s["date"] == day and s["time"] == time:
            if s["taken"]:
                return {"ok": False, "error": "slot already taken"}
            s["taken"] = True
            s["patient"] = patient
            return {"ok": True, "booking": dict(s)}
    return {"ok": False, "error": "no such slot"}


def check_order(order_id):
    o = ORDERS.get(str(order_id))
    if not o:
        return {"ok": False, "error": "unknown order id"}
    return {"ok": True, "order_id": str(order_id), **o}


def clinic_hours():
    return {"ok": True, "hours": "Monday to Saturday, 9 am to 7 pm"}


# weekday names -> offset, for parsing "tomorrow", "friday", ...
def resolve_day(word):
    today = date.today()
    if word == "today":
        return today.isoformat()
    if word == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    names = ["monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday"]
    if word in names:
        delta = (names.index(word) - today.weekday()) % 7
        if delta == 0:
            delta = 7
        return (today + timedelta(days=delta)).isoformat()
    return None
