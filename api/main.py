"""FastAPI app. Run:  uvicorn api.main:app --reload   (docs at /docs)"""
import csv
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from dateutil.rrule import rrulestr
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.loader import is_valid_email
from . import seed, worker
from .db import FMT, get_conn, init_db, iso, parse_dt


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop = worker.start_background(int(os.getenv("TICK_SECONDS", "30")))
    yield
    stop.set()


app = FastAPI(title="Email Automation & Reminder System", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])


class ContactIn(BaseModel):
    name: str
    email: str
    department: str = ""
    unsubscribed: bool = False


class TemplateIn(BaseModel):
    name: str
    subject: str
    body: str


class ReminderIn(BaseModel):
    title: str
    contact_id: int
    template_id: int
    event_date: str = ""
    event_time: str = ""
    send_at: str                      # ISO datetime; 'Z' or offset recommended (UTC stored)
    recurrence: str = "once"          # once | daily | weekly
    rrule: Optional[str] = None


def bad(msg, code=422):
    raise HTTPException(status_code=code, detail=msg)


@app.get("/health")
def health():
    return {"status": "ok", "dry_run": worker.is_dry_run()}


# ---------- contacts ----------
@app.get("/contacts")
def list_contacts():
    with get_conn() as db:
        return [dict(r) for r in db.execute("SELECT * FROM contacts ORDER BY id DESC")]


@app.post("/contacts", status_code=201)
def create_contact(c: ContactIn):
    if not c.name.strip():
        bad("Name is required")
    if not is_valid_email(c.email):
        bad("Invalid email address")
    try:
        with get_conn() as db:
            cur = db.execute("INSERT INTO contacts(name,email,department,unsubscribed) VALUES(?,?,?,?)",
                             (c.name.strip(), c.email.strip().lower(), c.department, int(c.unsubscribed)))
            return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        bad("A contact with this email already exists", 409)


@app.delete("/contacts/{cid}")
def delete_contact(cid: int):
    with get_conn() as db:
        db.execute("DELETE FROM contacts WHERE id=?", (cid,))
    return {"deleted": cid}


# ---------- templates ----------
@app.get("/templates")
def list_templates():
    with get_conn() as db:
        return [dict(r) for r in db.execute("SELECT * FROM templates ORDER BY id DESC")]


@app.post("/templates", status_code=201)
def create_template(t: TemplateIn):
    try:
        with get_conn() as db:
            cur = db.execute("INSERT INTO templates(name,subject,body) VALUES(?,?,?)",
                             (t.name.strip(), t.subject, t.body))
            return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        bad("A template with this name already exists", 409)


@app.delete("/templates/{tid}")
def delete_template(tid: int):
    try:
        with get_conn() as db:
            db.execute("DELETE FROM templates WHERE id=?", (tid,))
    except sqlite3.IntegrityError:
        bad("Template is used by a reminder - delete that reminder first", 409)
    return {"deleted": tid}


# ---------- reminders ----------
@app.get("/reminders")
def list_reminders():
    with get_conn() as db:
        rows = db.execute("""SELECT r.*, c.name contact_name, c.email contact_email,
                             t.name template_name FROM reminders r
                             JOIN contacts c ON c.id=r.contact_id
                             JOIN templates t ON t.id=r.template_id ORDER BY r.id DESC""")
        return [{**dict(r), "send_at": iso(r["send_at"])} for r in rows]


@app.post("/reminders", status_code=201)
def create_reminder(r: ReminderIn):
    if r.recurrence not in ("once", "daily", "weekly"):
        bad("recurrence must be once, daily or weekly")
    try:
        send_at = parse_dt(r.send_at)
    except ValueError:
        bad("send_at must be an ISO datetime, e.g. 2026-12-01T09:00:00Z")
    if r.rrule:
        try:
            rrulestr(r.rrule, dtstart=send_at)
        except Exception:
            bad("Invalid RRULE")
    try:
        with get_conn() as db:
            cur = db.execute("""INSERT INTO reminders(title,contact_id,template_id,event_date,
                                event_time,send_at,recurrence,rrule) VALUES(?,?,?,?,?,?,?,?)""",
                             (r.title, r.contact_id, r.template_id, r.event_date, r.event_time,
                              send_at.strftime(FMT), r.recurrence, r.rrule or None))
            return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        bad("Unknown contact_id or template_id")


@app.post("/reminders/{rid}/toggle")
def toggle_reminder(rid: int):
    with get_conn() as db:
        db.execute("UPDATE reminders SET active = 1 - active WHERE id=?", (rid,))
    return {"toggled": rid}


@app.delete("/reminders/{rid}")
def delete_reminder(rid: int):
    with get_conn() as db:
        db.execute("DELETE FROM reminders WHERE id=?", (rid,))
    return {"deleted": rid}


# ---------- messages, stats, actions ----------
def _messages(status: Optional[str], limit: int):
    q, args = "SELECT * FROM messages", []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with get_conn() as db:
        return [{**dict(r), "created_at": iso(r["created_at"]), "sent_at": iso(r["sent_at"]),
                 "occurrence": iso(r["occurrence"])} for r in db.execute(q, args)]


@app.get("/messages")
def list_messages(status: Optional[str] = None, limit: int = 100):
    return _messages(status, min(limit, 500))


@app.get("/messages/export.csv")
def export_messages():
    rows = _messages(None, 500)
    buf = io.StringIO()
    cols = ["id", "reminder_id", "occurrence", "to_name", "to_email", "subject",
            "status", "mode", "attempts", "error", "created_at", "sent_at"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=report.csv"})


@app.get("/stats")
def stats():
    with get_conn() as db:
        by = {r["status"]: r["n"] for r in
              db.execute("SELECT status, COUNT(*) n FROM messages GROUP BY status")}
        count = lambda t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return {"messages": by, "contacts": count("contacts"), "templates": count("templates"),
                "reminders": count("reminders"), "dry_run": worker.is_dry_run()}


@app.post("/run-now")
def run_now():
    return worker.tick()


@app.post("/demo/load")
def load_demo():
    return seed.load_demo()
