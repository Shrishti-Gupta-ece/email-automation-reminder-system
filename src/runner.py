"""Core engine: decide which reminders are due, render, send, log, report."""
from datetime import datetime, timedelta
from . import config, reporter
from .loader import load_contacts, load_reminders
from .templating import render
from .mailer import build_message, send_smtp, save_preview


def due_occurrence(send_at, recurrence, now):
    """Latest firing time <= now for once / daily / weekly reminders (else None)."""
    if send_at is None or str(send_at) == "NaT" or send_at > now:
        return None
    if recurrence == "daily":
        return send_at + timedelta(days=(now - send_at).days)
    if recurrence == "weekly":
        return send_at + timedelta(weeks=(now - send_at).days // 7)
    return send_at


def run_once(dry_run: bool, force_all: bool, log, sent_log, failed_log):
    """One pass over all reminders. Returns counts dict."""
    mode = "DRY_RUN" if dry_run else "LIVE"
    ok_status = "DRY_RUN" if dry_run else "SENT"
    now = datetime.now()
    contacts = load_contacts(config.CONTACTS_FILE, log)
    reminders = load_reminders(config.REMINDERS_FILE, log)
    done = set() if force_all else reporter.already_done(ok_status)
    counts = {"sent": 0, "failed": 0, "skipped": 0}

    for r in reminders:
        rid = r["reminder_id"]
        occ = r["send_at"] if force_all else due_occurrence(r["send_at"], r["recurrence"], now)
        if occ is None or str(occ) == "NaT":
            continue                                   # not due yet
        occ_str = occ.strftime("%Y-%m-%d %H:%M")
        if f"{rid}|{occ_str}" in done:
            continue                                   # idempotency: already handled

        base = {"reminder_id": rid, "occurrence": occ_str, "email": r["email"], "mode": mode}
        contact = contacts.get(r["email"])
        if contact is None:
            err = "Contact not found or invalid email"
            failed_log.error(f"{rid} -> {r['email']} | {err}")
            reporter.write_row({**base, "name": "", "status": "FAILED", "error": err})
            counts["failed"] += 1
            continue
        if contact["unsubscribed"]:
            log.info(f"{rid} skipped: {r['email']} is unsubscribed")
            reporter.write_row({**base, "name": contact["name"], "status": "SKIPPED",
                                "error": "Unsubscribed"})
            counts["skipped"] += 1
            continue

        values = {"name": contact["name"], "department": contact.get("department", ""),
                  "title": r["title"], "event_date": r["event_date"], "event_time": r["event_time"]}
        try:
            subject, body = render(r["template"], values)
            msg = build_message(r["email"], contact["name"], subject, body)
            if dry_run:
                path = save_preview(msg, rid)
                log.info(f"[DRY RUN] {rid} -> {r['email']} | {subject} (preview: {path.name})")
            else:
                send_smtp(msg)
                log.info(f"[SENT] {rid} -> {r['email']} | {subject}")
            sent_log.info(f"{rid} -> {r['email']} | {subject} | {mode}")
            reporter.write_row({**base, "name": contact["name"], "subject": subject,
                                "status": ok_status})
            counts["sent"] += 1
        except Exception as e:                         # one bad email must not stop the batch
            log.error(f"[FAILED] {rid} -> {r['email']} | {e}")
            failed_log.error(f"{rid} -> {r['email']} | {e}")
            reporter.write_row({**base, "name": contact["name"], "status": "FAILED",
                                "error": str(e)})
            counts["failed"] += 1
    log.info(f"Run complete: {counts}")
    return counts
