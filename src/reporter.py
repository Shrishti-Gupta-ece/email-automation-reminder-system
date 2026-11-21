"""Append one row per attempt to outputs/report.csv and read previous results."""
import csv
from datetime import datetime
from .config import REPORT_FILE, OUTPUTS_DIR

FIELDS = ["timestamp", "reminder_id", "occurrence", "name", "email",
          "subject", "status", "mode", "error"]


def write_row(row: dict):
    OUTPUTS_DIR.mkdir(exist_ok=True)
    new_file = not REPORT_FILE.exists()
    row = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **row}
    with open(REPORT_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def already_done(status: str) -> set:
    """Keys already handled: success, skipped, or failed 3+ times."""
    if not REPORT_FILE.exists():
        return set()
    done, fails = set(), {}
    with open(REPORT_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = f"{r['reminder_id']}|{r['occurrence']}"
            if r["status"] in (status, "SKIPPED"):
                done.add(key)
            elif r["status"] == "FAILED":
                fails[key] = fails.get(key, 0) + 1
    done.update(k for k, n in fails.items() if n >= 3)
    return done