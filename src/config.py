"""Central configuration. Secrets come from environment variables (.env), never from code."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

CONTACTS_FILE = BASE_DIR / "data" / "contacts.csv"
REMINDERS_FILE = BASE_DIR / "data" / "reminders.csv"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUTS_DIR = BASE_DIR / "outputs"
PREVIEWS_DIR = OUTPUTS_DIR / "previews"
LOGS_DIR = BASE_DIR / "logs"
REPORT_FILE = OUTPUTS_DIR / "report.csv"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SENDER_NAME = os.getenv("SENDER_NAME", "Reminder System")
