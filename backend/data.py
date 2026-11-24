"""Mock clinic data (in-memory) and the three tool implementations."""
import re, datetime as dt, itertools

DOCTORS = [
    {"id": "d1", "name": "Dr. Asha Rao", "speciality": "Cardiology"},
    {"id": "d2", "name": "Dr. Imran Shaikh", "speciality": "Dermatology"},
    {"id": "d3", "name": "Dr. Meera Nair", "speciality": "Pediatrics"},
    {"id": "d4", "name": "Dr. Rohan Kulkarni", "speciality": "Orthopedics"},
]
TIMES = ["09:00", "10:30", "12:00", "15:00", "16:30"]
SLOTS = [  # next 3 days for every doctor
    {"doctor_id": d["id"], "date": (dt.date.today() + dt.timedelta(days=i)).isoformat(), "time": t, "booked": False}
    for d in DOCTORS for i in range(1, 4) for t in TIMES
]
APPOINTMENTS = []
_ids = itertools.count(1)


def norm_phone(p):
    return re.sub(r"\D", "", p or "")[-10:]


def find_doctor(q):
    q = (q or "").lower().strip()
    for d in DOCTORS:
        if q and (q == d["id"] or q in d["name"].lower() or q in d["speciality"].lower()):
            return d
    return None


def check_doctor_availability(doctor=None, date=None, **_):
    d = find_doctor(doctor) if doctor else None
    if doctor and not d:
        return {"error": "Doctor not found", "doctors": [f'{x["name"]} ({x["speciality"]})' for x in DOCTORS]}
    free = [s for s in SLOTS if not s["booked"] and (not d or s["doctor_id"] == d["id"]) and (not date or s["date"] == date)]
    names = {x["id"]: x["name"] for x in DOCTORS}
    return {"slots": [{"doctor": names[s["doctor_id"]], "date": s["date"], "time": s["time"]} for s in free[:10]],
            "total_free": len(free)}


def book_appointment(doctor, date, time, phone, patient_name="Caller", **_):
    p = norm_phone(phone)
    d = find_doctor(doctor)
    if len(p) != 10:
        return {"error": "Phone number must have 10 digits"}
    if not d:
        return {"error": "Doctor not found"}
    s = next((s for s in SLOTS if s["doctor_id"] == d["id"] and s["date"] == date and s["time"] == time), None)
    if not s or s["booked"]:
        return {"error": "Slot not available"}
    s["booked"] = True
    a = {"id": next(_ids), "doctor_id": d["id"], "doctor": d["name"], "speciality": d["speciality"],
         "date": date, "time": time, "phone": p, "patient": patient_name}
    APPOINTMENTS.append(a)
    return {"status": "booked", **a}


def cancel_appointment(phone, date=None, time=None, **_):
    p = norm_phone(phone)
    mine = [a for a in APPOINTMENTS if a["phone"] == p and (not date or a["date"] == date) and (not time or a["time"] == time)]
    if not mine:
        return {"error": "No appointment found for this number"}
    if len(mine) > 1:
        return {"error": "Multiple appointments, ask which one", "appointments": [(a["doctor"], a["date"], a["time"]) for a in mine]}
    a = mine[0]
    APPOINTMENTS.remove(a)
    for s in SLOTS:
        if (s["doctor_id"], s["date"], s["time"]) == (a["doctor_id"], a["date"], a["time"]):
            s["booked"] = False
    return {"status": "cancelled", "doctor": a["doctor"], "date": a["date"], "time": a["time"]}
