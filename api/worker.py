"""Engine: plan due reminders into messages, then dispatch queued messages."""
import logging
import os
import smtplib
import threading
from datetime import timedelta

from dateutil.rrule import rrulestr

from src.mailer import build_message, send_smtp
from src.templating import fill
from .db import FMT, from_db, get_conn, utcnow

log = logging.getLogger("worker")
MAX_ATTEMPTS = 3
_lock = threading.Lock()


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "true").lower() != "false"


def due_occurrence(send_at, recurrence, rrule, now):
    """Latest firing time <= now, or None if the reminder is not due yet."""
    if send_at > now:
        return None
    if rrule:
        return rrulestr(rrule, dtstart=send_at).before(now, inc=True)
    if recurrence == "daily":
        return send_at + timedelta(days=(now - send_at).days)
    if recurrence == "weekly":
        return send_at + timedelta(weeks=(now - send_at).days // 7)
    return send_at


PLAN_SQL = """
SELECT r.id, r.title, r.event_date, r.event_time, r.send_at, r.recurrence, r.rrule,
       c.name cname, c.email cemail, c.department cdept, c.unsubscribed cunsub,
       t.subject tsub, t.body tbody
FROM reminders r
JOIN contacts c ON c.id = r.contact_id
JOIN templates t ON t.id = r.template_id
WHERE r.active = 1
"""


def plan(conn, now) -> int:
    """Create one message per due reminder firing (skips ones that already exist)."""
    created = 0
    for r in conn.execute(PLAN_SQL).fetchall():
        try:
            occ = due_occurrence(from_db(r["send_at"]), r["recurrence"], r["rrule"], now)
        except Exception as e:
            log.warning("Bad schedule on reminder %s: %s", r["id"], e)
            continue
        if occ is None:
            continue
        occ_s = occ.strftime(FMT)
        if conn.execute("SELECT 1 FROM messages WHERE reminder_id=? AND occurrence=?",
                        (r["id"], occ_s)).fetchone():
            continue
        status, error, subject, body, attempts = "queued", None, None, None, 0
        if r["cunsub"]:
            status, error = "skipped", "Unsubscribed"
        else:
            values = {"name": r["cname"], "department": r["cdept"], "title": r["title"],
                      "event_date": r["event_date"], "event_time": r["event_time"]}
            try:
                subject, body = fill(r["tsub"], values), fill(r["tbody"], values)
            except Exception as e:                       # e.g. missing placeholder
                status, error, attempts = "failed", str(e), MAX_ATTEMPTS
        conn.execute(
            """INSERT OR IGNORE INTO messages(reminder_id, occurrence, to_email, to_name,
               subject, body, status, attempts, error, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (r["id"], occ_s, r["cemail"], r["cname"], subject, body, status, attempts,
             error, now.strftime(FMT)))
        created += 1
    conn.commit()
    return created


def dispatch(conn, now) -> dict:
    """Send (or dry-run) queued messages; retry failed ones up to MAX_ATTEMPTS."""
    out = {"sent": 0, "failed": 0}
    mode = "dry_run" if is_dry_run() else "live"
    rows = conn.execute("SELECT * FROM messages WHERE status IN ('queued','failed') "
                        "AND attempts < ? ORDER BY id", (MAX_ATTEMPTS,)).fetchall()
    for m in rows:
        attempts = m["attempts"] + 1
        try:
            if mode == "dry_run":
                status = "dry_run"
            else:
                msg = build_message(m["to_email"], m["to_name"], m["subject"], m["body"])
                send_smtp(msg, retries=1)
                status = "sent"
            conn.execute("UPDATE messages SET status=?, attempts=?, error=NULL, mode=?, "
                         "sent_at=? WHERE id=?",
                         (status, attempts, mode, now.strftime(FMT), m["id"]))
            out["sent"] += 1
            log.info("[%s] message %s -> %s", status.upper(), m["id"], m["to_email"])
        except (smtplib.SMTPAuthenticationError, RuntimeError) as e:
            # wrong / missing credentials: retrying will not help
            conn.execute("UPDATE messages SET status='failed', attempts=?, error=?, mode=? "
                         "WHERE id=?", (MAX_ATTEMPTS, str(e), mode, m["id"]))
            out["failed"] += 1
            log.error("[FAILED] message %s: %s", m["id"], e)
        except Exception as e:
            conn.execute("UPDATE messages SET status='failed', attempts=?, error=?, mode=? "
                         "WHERE id=?", (attempts, str(e), mode, m["id"]))
            out["failed"] += 1
            log.error("[FAILED] message %s: %s", m["id"], e)
        conn.commit()          # commit per message so the API is never blocked for long
    return out


def tick(now=None) -> dict:
    """One scheduler cycle. A lock stops the background loop and /run-now overlapping."""
    with _lock:
        now = now or utcnow()
        with get_conn() as conn:
            created = plan(conn, now)
            result = dispatch(conn, now)
        return {"planned": created, **result, "mode": "dry_run" if is_dry_run() else "live"}


def start_background(interval: int = 30) -> threading.Event:
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                log.exception("tick failed")
            stop.wait(interval)

    threading.Thread(target=loop, daemon=True, name="scheduler").start()
    return stop
