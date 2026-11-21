'use client'
import { useCallback, useEffect, useState } from 'react'

// All calls go to /api/* which next.config.js proxies to FastAPI (port 8000)
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch (e) {}
    throw new Error(msg)
  }
  return res.json()
}

const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body || {}) })
const del = (path) => api(path, { method: 'DELETE' })
const fmt = (s) => (s ? new Date(s).toLocaleString() : '-')
const pad = (n) => String(n).padStart(2, '0')
const localInput = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`

export default function Home() {
  const [tab, setTab] = useState('messages')
  const [stats, setStats] = useState(null)
  const [messages, setMessages] = useState([])
  const [contacts, setContacts] = useState([])
  const [templates, setTemplates] = useState([])
  const [reminders, setReminders] = useState([])
  const [notice, setNotice] = useState('')

  const [cForm, setCForm] = useState({ name: '', email: '', department: '' })
  const [tForm, setTForm] = useState({ name: '', subject: '', body: '' })
  const [rForm, setRForm] = useState({
    title: '', contact_id: '', template_id: '',
    event_date: '', event_time: '', send_at: '', recurrence: 'once',
  })

  const refresh = useCallback(async () => {
    try {
      const [s, m, c, t, r] = await Promise.all([
        api('/stats'), api('/messages'), api('/contacts'), api('/templates'), api('/reminders'),
      ])
      setStats(s); setMessages(m); setContacts(c); setTemplates(t); setReminders(r)
    } catch (e) {
      setNotice('Cannot reach the API. Is FastAPI running on port 8000? (' + e.message + ')')
    }
  }, [])

  useEffect(() => {
    refresh()
    setRForm((f) => ({ ...f, send_at: localInput(new Date(Date.now() + 2 * 60 * 1000)) }))
    const id = setInterval(refresh, 5000)   // auto-refresh every 5 s
    return () => clearInterval(id)
  }, [refresh])

  // run an action, show a message, then reload data
  async function act(fn, okMsg) {
    try {
      const out = await fn()
      setNotice(typeof okMsg === 'function' ? okMsg(out) : okMsg)
    } catch (e) {
      setNotice('Error: ' + e.message)
    }
    refresh()
  }

  const sentCount = stats ? (stats.messages.sent || 0) + (stats.messages.dry_run || 0) : 0

  return (
    <div className="wrap">
      <h1>Email Automation &amp; Reminder System</h1>
      <div className="sub">
        Mode: <b>{stats ? (stats.dry_run ? 'DRY-RUN (no real emails)' : 'LIVE') : '...'}</b>
      </div>

      <div className="row">
        <button className="btn" onClick={() => act(() => post('/demo/load'),
          (o) => `Demo loaded: ${o.contacts} contacts, ${o.templates} templates, ${o.reminders} reminders. Skipped: ${o.skipped.length}`)}>
          Load demo data
        </button>
        <button className="btn alt" onClick={() => act(() => post('/run-now'),
          (o) => `Run complete: planned ${o.planned}, processed ${o.sent}, failed ${o.failed}`)}>
          Run scheduler now
        </button>
        <a className="btn alt" style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid var(--line)', color: 'inherit', textDecoration: 'none' }}
           href="/api/messages/export.csv">Download CSV report</a>
      </div>

      {notice && <div className="notice">{notice}</div>}

      {stats && (
        <div className="cards">
          <div className="card"><b>{stats.contacts}</b><span>Contacts</span></div>
          <div className="card"><b>{stats.templates}</b><span>Templates</span></div>
          <div className="card"><b>{stats.reminders}</b><span>Reminders</span></div>
          <div className="card"><b>{sentCount}</b><span>Sent / dry-run</span></div>
          <div className="card"><b>{stats.messages.queued || 0}</b><span>Queued</span></div>
          <div className="card"><b>{stats.messages.failed || 0}</b><span>Failed</span></div>
          <div className="card"><b>{stats.messages.skipped || 0}</b><span>Skipped</span></div>
        </div>
      )}

      <div className="tabs">
        {['messages', 'reminders', 'contacts', 'templates'].map((t) => (
          <button key={t} className={'tab' + (tab === t ? ' on' : '')} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'messages' && (
        <div className="panel table-wrap">
          <table>
            <thead><tr><th>ID</th><th>To</th><th>Subject</th><th>Status</th><th>Time</th><th>Error</th><th>Body</th></tr></thead>
            <tbody>
              {messages.map((m) => (
                <tr key={m.id}>
                  <td>{m.id}</td>
                  <td>{m.to_name}<br /><small>{m.to_email}</small></td>
                  <td>{m.subject || '-'}</td>
                  <td><span className={'badge ' + m.status}>{m.status}</span></td>
                  <td>{fmt(m.sent_at || m.created_at)}</td>
                  <td>{m.error || ''}</td>
                  <td>{m.body ? <details><summary>view</summary><pre>{m.body}</pre></details> : ''}</td>
                </tr>
              ))}
              {messages.length === 0 && <tr><td colSpan="7">No messages yet. Click "Load demo data".</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'reminders' && (
        <>
          <div className="panel">
            <div className="row">
              <input placeholder="Title" value={rForm.title} onChange={(e) => setRForm({ ...rForm, title: e.target.value })} />
              <select value={rForm.contact_id} onChange={(e) => setRForm({ ...rForm, contact_id: e.target.value })}>
                <option value="">Contact...</option>
                {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={rForm.template_id} onChange={(e) => setRForm({ ...rForm, template_id: e.target.value })}>
                <option value="">Template...</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <input type="date" value={rForm.event_date} onChange={(e) => setRForm({ ...rForm, event_date: e.target.value })} />
              <input placeholder="Event time e.g. 7:00 PM" value={rForm.event_time} onChange={(e) => setRForm({ ...rForm, event_time: e.target.value })} />
              <input type="datetime-local" value={rForm.send_at} onChange={(e) => setRForm({ ...rForm, send_at: e.target.value })} />
              <select value={rForm.recurrence} onChange={(e) => setRForm({ ...rForm, recurrence: e.target.value })}>
                <option value="once">once</option>
                <option value="daily">daily</option>
                <option value="weekly">weekly</option>
              </select>
              <button className="btn" onClick={() => act(() => post('/reminders', {
                ...rForm,
                contact_id: Number(rForm.contact_id),
                template_id: Number(rForm.template_id),
                send_at: new Date(rForm.send_at).toISOString(),   // local time -> UTC
              }), 'Reminder scheduled')}>Schedule</button>
            </div>
          </div>
          <div className="panel table-wrap">
            <table>
              <thead><tr><th>Title</th><th>Contact</th><th>Template</th><th>First send</th><th>Repeat</th><th>Active</th><th></th></tr></thead>
              <tbody>
                {reminders.map((r) => (
                  <tr key={r.id}>
                    <td>{r.title}</td>
                    <td>{r.contact_name}</td>
                    <td>{r.template_name}</td>
                    <td>{fmt(r.send_at)}</td>
                    <td>{r.rrule || r.recurrence}</td>
                    <td><button className="btn alt" onClick={() => act(() => post(`/reminders/${r.id}/toggle`), 'Updated')}>{r.active ? 'on' : 'off'}</button></td>
                    <td><button className="link" onClick={() => act(() => del(`/reminders/${r.id}`), 'Reminder deleted')}>delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'contacts' && (
        <>
          <div className="panel row">
            <input placeholder="Name" value={cForm.name} onChange={(e) => setCForm({ ...cForm, name: e.target.value })} />
            <input placeholder="Email" value={cForm.email} onChange={(e) => setCForm({ ...cForm, email: e.target.value })} />
            <input placeholder="Department" value={cForm.department} onChange={(e) => setCForm({ ...cForm, department: e.target.value })} />
            <button className="btn" onClick={() => act(async () => {
              await post('/contacts', cForm)
              setCForm({ name: '', email: '', department: '' })
            }, 'Contact added')}>Add contact</button>
          </div>
          <div className="panel table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Dept</th><th>Unsubscribed</th><th></th></tr></thead>
              <tbody>
                {contacts.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td><td>{c.email}</td><td>{c.department}</td>
                    <td>{c.unsubscribed ? 'yes' : 'no'}</td>
                    <td><button className="link" onClick={() => act(() => del(`/contacts/${c.id}`), 'Contact deleted')}>delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'templates' && (
        <>
          <div className="panel">
            <div className="row" style={{ marginBottom: 8 }}>
              <input placeholder="Template name" value={tForm.name} onChange={(e) => setTForm({ ...tForm, name: e.target.value })} />
              <input style={{ flex: 1 }} placeholder="Subject e.g. Reminder: {{title}}" value={tForm.subject} onChange={(e) => setTForm({ ...tForm, subject: e.target.value })} />
            </div>
            <textarea placeholder={'Body. Use {{name}}, {{title}}, {{event_date}}, {{event_time}}, {{department}}'} value={tForm.body} onChange={(e) => setTForm({ ...tForm, body: e.target.value })} />
            <div style={{ marginTop: 8 }}>
              <button className="btn" onClick={() => act(async () => {
                await post('/templates', tForm)
                setTForm({ name: '', subject: '', body: '' })
              }, 'Template saved')}>Save template</button>
            </div>
          </div>
          <div className="panel table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Subject</th><th>Body</th><th></th></tr></thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id}>
                    <td>{t.name}</td><td>{t.subject}</td>
                    <td><details><summary>view</summary><pre>{t.body}</pre></details></td>
                    <td><button className="link" onClick={() => act(() => del(`/templates/${t.id}`), 'Template deleted')}>delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
