# Email Automation & Reminder System

A beginner-friendly Python project that reads contacts and reminders from CSV files, personalizes email templates, schedules reminders (once / daily / weekly), sends via SMTP, and produces logs and a CSV report. Includes a safe **dry-run mode** (default) so you can test without sending real emails.

## Features
- CSV contacts and reminders (Pandas)
- Template placeholders like `{{name}}`, `{{title}}`
- Dry-run mode saving `.eml` previews
- Recurring reminders: once, daily, weekly
- Duplicate-send protection (idempotency)
- Skips unsubscribed contacts, validates emails
- Separate `sent.log` / `failed.log`, plus `outputs/report.csv`
- Secrets via `.env` (never committed)

## Setup
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```
Optional for real sending: copy `.env.example` to `.env` and add your Gmail App Password.

## Run
```bash
python main.py --all          # dry-run, all reminders
python main.py                # dry-run, only due reminders
python main.py --schedule     # keep checking every minute
python main.py --live         # real emails
```

## Folder structure
```
data/ templates/ src/ outputs/ logs/ images/ docs/ main.py requirements.txt .env.example
```

## Sample output
```
[DRY RUN] R001 -> aarav.sharma@example.com | Reminder: Python Live Class on 2026-11-22 at 7:00 PM
R005 skipped: karan.singh@example.com is unsubscribed
[FAILED] R008 -> priya.verma@example.com | Template 'missing_template' not found
Run complete: {'sent': 5, 'failed': 2, 'skipped': 1}
```

## Screenshots
Add to `images/` and link here.

## Learning outcomes
File handling, Pandas, SMTP/email, scheduling, logging, error handling, secure config, Git/GitHub workflow.

## Future improvements
FastAPI backend, SQLite/Postgres, Next.js dashboard, retries queue, open tracking, ICS invites.
