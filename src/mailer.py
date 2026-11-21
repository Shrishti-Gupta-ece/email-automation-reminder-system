"""Build and send emails via SMTP (smtplib + email.message)."""
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr
from . import config


def build_message(to_email, to_name, subject, body):
    msg = EmailMessage()
    msg["From"] = formataddr((config.SENDER_NAME, config.SMTP_USER or "noreply@example.com"))
    msg["To"] = formataddr((to_name, to_email))
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def save_preview(msg, reminder_id):
    """Dry-run helper: write the email to outputs/previews/ as an .eml file."""
    config.PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PREVIEWS_DIR / f"{reminder_id}.eml"
    path.write_bytes(bytes(msg))
    return path


def send_smtp(msg, retries=3):
    """Send for real. Retries on temporary errors, stops on auth errors."""
    if not config.SMTP_USER or not config.SMTP_PASS:
        raise RuntimeError("SMTP_USER / SMTP_PASS not set. Create a .env file (see .env.example).")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASS)
                server.send_message(msg)
            return
        except smtplib.SMTPAuthenticationError:
            raise                      # wrong password: retrying will not help
        except (smtplib.SMTPException, OSError) as e:
            last_err = e
            time.sleep(2 * attempt)    # simple backoff
    raise last_err
