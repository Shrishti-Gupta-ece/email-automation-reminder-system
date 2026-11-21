## Full-stack version (FastAPI + SQLite + Next.js)

```
Browser (Next.js :3000)  --/api proxy-->  FastAPI (:8000)  -->  SQLite (db/email.db)
                                              |
                                  background scheduler thread (every 30s)
                                  plan(): due reminders -> messages (unique per firing)
                                  dispatch(): render -> SMTP or dry-run -> status
```

### Run
```bash
# Terminal 1 (project root, venv active)
pip install -r requirements.txt
uvicorn api.main:app --reload          # API docs: http://127.0.0.1:8000/docs

# Terminal 2
cd web
npm install
npm run dev                            # Dashboard: http://localhost:3000
```
Click **Load demo data** on the dashboard; messages appear one per minute.
Default mode is DRY-RUN. Set `DRY_RUN=false` in `.env` (with SMTP creds) for real emails.

### Tests
```bash
python -m unittest discover tests -v
```

### Design notes
- Times stored in UTC; browser shows local time.
- `UNIQUE(reminder_id, occurrence)` makes scheduling idempotent (no duplicate sends).
- Failed sends retry up to 3 times; auth errors are not retried.
- Recurrence: once / daily / weekly, or any RFC 5545 RRULE via the API.
- Unsubscribed contacts are skipped; every attempt is auditable in the messages table.
