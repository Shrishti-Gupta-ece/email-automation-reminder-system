"""Logging: one general log, plus separate sent.log and failed.log files."""
import logging
from .config import LOGS_DIR

FMT = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")


def _make(name, filename, console=False):
    lg = logging.getLogger(name)
    if lg.handlers:            # avoid duplicate handlers
        return lg
    lg.setLevel(logging.INFO)
    LOGS_DIR.mkdir(exist_ok=True)
    fh = logging.FileHandler(LOGS_DIR / filename, encoding="utf-8")
    fh.setFormatter(FMT)
    lg.addHandler(fh)
    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(FMT)
        lg.addHandler(ch)
    return lg


def get_loggers():
    main = _make("app", "email_automation.log", console=True)
    sent = _make("sent", "sent.log")
    failed = _make("failed", "failed.log")
    return main, sent, failed
