"""Run:  python -m unittest discover tests -v   (no network, no real emails)"""
import os
import tempfile
import unittest
from datetime import datetime

os.environ["EMAIL_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DRY_RUN"] = "true"

from api import seed, worker                 # noqa: E402
from api.db import get_conn, init_db          # noqa: E402


class EngineTests(unittest.TestCase):
    def setUp(self):
        with get_conn() as db:
            db.executescript("DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS reminders;"
                             "DROP TABLE IF EXISTS templates; DROP TABLE IF EXISTS contacts;")
        init_db()
        with get_conn() as db:
            db.execute("INSERT INTO contacts(name,email,department,unsubscribed) VALUES"
                       "('Asha','asha@example.com','HR',0),('Bob','bob@example.com','HR',1)")
            db.execute("INSERT INTO templates(name,subject,body) VALUES"
                       "('ok','Hi {{name}}: {{title}}','Body for {{name}}'),"
                       "('bad','Hi {{name}}','Missing {{nothing}}')")

    def add(self, cid, tid, send_at, recurrence="once"):
        with get_conn() as db:
            db.execute("INSERT INTO reminders(title,contact_id,template_id,send_at,recurrence) "
                       "VALUES('Demo',?,?,?,?)", (cid, tid, send_at, recurrence))

    def statuses(self):
        with get_conn() as db:
            return [r["status"] for r in db.execute("SELECT status FROM messages ORDER BY id")]

    def test_due_reminder_is_sent_once(self):
        self.add(1, 1, "2026-01-01 09:00:00")
        now = datetime(2026, 1, 1, 9, 5)
        self.assertEqual(worker.tick(now)["sent"], 1)
        worker.tick(now)                      # second tick must not duplicate
        self.assertEqual(self.statuses(), ["dry_run"])

    def test_future_reminder_waits(self):
        self.add(1, 1, "2026-01-02 09:00:00")
        worker.tick(datetime(2026, 1, 1, 9, 0))
        self.assertEqual(self.statuses(), [])

    def test_unsubscribed_is_skipped(self):
        self.add(2, 1, "2026-01-01 09:00:00")
        worker.tick(datetime(2026, 1, 1, 10, 0))
        self.assertEqual(self.statuses(), ["skipped"])

    def test_missing_placeholder_fails(self):
        self.add(1, 2, "2026-01-01 09:00:00")
        worker.tick(datetime(2026, 1, 1, 10, 0))
        self.assertEqual(self.statuses(), ["failed"])

    def test_daily_recurrence(self):
        self.add(1, 1, "2026-01-01 09:00:00", "daily")
        worker.tick(datetime(2026, 1, 1, 9, 1))
        worker.tick(datetime(2026, 1, 2, 9, 1))
        worker.tick(datetime(2026, 1, 3, 9, 1))
        self.assertEqual(self.statuses(), ["dry_run"] * 3)

    def test_rrule(self):
        with get_conn() as db:
            db.execute("INSERT INTO reminders(title,contact_id,template_id,send_at,rrule) VALUES"
                       "('R',1,1,'2026-01-05 09:00:00','FREQ=WEEKLY;BYDAY=MO,WE')")
        for d in (5, 6, 7):                   # Mon, Tue, Wed
            worker.tick(datetime(2026, 1, d, 9, 30))
        self.assertEqual(len(self.statuses()), 2)   # Mon + Wed only

    def test_demo_seed(self):
        res = seed.load_demo()
        self.assertGreater(res["contacts"], 0)
        self.assertGreater(res["reminders"], 0)
        self.assertEqual(len(res["skipped"]), 2)    # ghost contact + missing template


if __name__ == "__main__":
    unittest.main()
