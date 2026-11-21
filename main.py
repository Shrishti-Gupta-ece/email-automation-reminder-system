"""Email Automation & Reminder System - entry point.

Examples:
  python main.py --all                 # dry-run, process every reminder (safe demo)
  python main.py                       # dry-run, only reminders that are due now
  python main.py --schedule            # dry-run, keep checking every minute
  python main.py --live                # REAL emails (needs .env)
  python main.py --live --schedule     # REAL emails, run continuously
"""
import argparse
import time
from src.logger_setup import get_loggers
from src.runner import run_once


def main():
    p = argparse.ArgumentParser(description="Email Automation & Reminder System")
    p.add_argument("--live", action="store_true", help="Send real emails (default is dry-run)")
    p.add_argument("--all", action="store_true", help="Ignore send time and process all reminders")
    p.add_argument("--schedule", action="store_true", help="Keep running and check periodically")
    p.add_argument("--interval", type=int, default=1, help="Minutes between checks (default 1)")
    args = p.parse_args()

    log, sent_log, failed_log = get_loggers()
    dry_run = not args.live
    log.info(f"Starting in {'DRY-RUN' if dry_run else 'LIVE'} mode")

    job = lambda: run_once(dry_run, args.all, log, sent_log, failed_log)
    job()
    if args.schedule:
        import schedule  # imported here so dry-run works even before installing it
        schedule.every(args.interval).minutes.do(job)
        log.info(f"Scheduler running every {args.interval} min. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Stopped by user.")


if __name__ == "__main__":
    main()
