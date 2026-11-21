"""Load the CSV demo data (data/ + templates/) into SQLite."""
import logging
from datetime import timedelta

from src import config
from src.loader import load_contacts, load_reminders
from src.templating import load_template
from .db import FMT, get_conn, utcnow


def load_demo() -> dict:
    log = logging.getLogger("seed")
    result = {"contacts": 0, "templates": 0, "reminders": 0, "skipped": []}
    with get_conn() as conn:
        for c in load_contacts(config.CONTACTS_FILE, log).values():
            cur = conn.execute("INSERT OR IGNORE INTO contacts(name,email,department,unsubscribed)"
                               " VALUES(?,?,?,?)",
                               (c["name"], c["email"], c.get("department", ""), int(c["unsubscribed"])))
            result["contacts"] += cur.rowcount
        for path in sorted(config.TEMPLATES_DIR.glob("*.txt")):
            subject, body = load_template(path.stem)
            cur = conn.execute("INSERT OR IGNORE INTO templates(name,subject,body) VALUES(?,?,?)",
                               (path.stem, subject, body))
            result["templates"] += cur.rowcount

        # Demo reminders fire starting 1 minute ago, then one per minute,
        # so the dashboard shows messages appearing live on any day.
        start = utcnow() - timedelta(minutes=1)
        for r in load_reminders(config.REMINDERS_FILE, log):
            c = conn.execute("SELECT id FROM contacts WHERE email=?", (r["email"],)).fetchone()
            t = conn.execute("SELECT id FROM templates WHERE name=?", (r["template"],)).fetchone()
            if not c or not t:
                result["skipped"].append(f"{r['reminder_id']}: unknown contact or template")
                continue
            if conn.execute("SELECT 1 FROM reminders WHERE title=? AND contact_id=?",
                            (r["title"], c["id"])).fetchone():
                continue
            send_at = start + timedelta(minutes=result["reminders"])
            conn.execute("""INSERT INTO reminders(title,contact_id,template_id,event_date,
                            event_time,send_at,recurrence) VALUES(?,?,?,?,?,?,?)""",
                         (r["title"], c["id"], t["id"], r["event_date"], r["event_time"],
                          send_at.strftime(FMT), r["recurrence"] or "once"))
            result["reminders"] += 1
    return result
