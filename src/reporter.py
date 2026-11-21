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
    """Keys (reminder_id|occurrence) already completed - prevents duplicate sends."""
    if not REPORT_FILE.exists():
        return set()
    with open(REPORT_FILE, newline="", encoding="utf-8") as f:
        return {f"{r['reminder_id']}|{r['occurrence']}" for r in csv.DictReader(f)
                if r["status"] == status}
