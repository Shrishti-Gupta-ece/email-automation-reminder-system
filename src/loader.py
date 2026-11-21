"""Read and validate contacts and reminders from CSV using pandas."""
import re
import pandas as pd

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(str(email).strip()))


def load_contacts(path, log):
    """Return dict {email: contact_dict}. Invalid / unsubscribed rows are flagged."""
    df = pd.read_csv(path, dtype=str).fillna("")
    df["email"] = df["email"].str.strip().str.lower()
    df = df.drop_duplicates(subset="email")
    contacts = {}
    for row in df.to_dict("records"):
        if not is_valid_email(row["email"]):
            log.warning(f"Skipping invalid email in contacts: {row['email']!r}")
            continue
        row["unsubscribed"] = row.get("unsubscribed", "no").strip().lower() in ("yes", "true", "1")
        contacts[row["email"]] = row
    log.info(f"Loaded {len(contacts)} valid contacts")
    return contacts


def load_reminders(path, log):
    df = pd.read_csv(path, dtype=str).fillna("")
    df["email"] = df["email"].str.strip().str.lower()
    df["send_at"] = pd.to_datetime(df["send_at"], errors="coerce")
    df["recurrence"] = df["recurrence"].str.strip().str.lower().replace("", "once")
    log.info(f"Loaded {len(df)} reminders")
    return df.to_dict("records")
