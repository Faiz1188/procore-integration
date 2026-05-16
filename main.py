import os
import httpx
from datetime import date, timedelta
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

load_dotenv()
app = FastAPI()

# Database se connect karo
def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Procore se token lo
def get_token():
    r = httpx.post("https://login.procore.com/oauth/token", json={
        "grant_type": "client_credentials",
        "client_id": os.getenv("PROCORE_CLIENT_ID"),
        "client_secret": os.getenv("PROCORE_CLIENT_SECRET"),
    })
    return r.json()["access_token"]

# Procore webhook yahan aayega
@app.post("/webhooks/procore")
async def procore_webhook(request: Request):
    payload = await request.json()
    resource = payload.get("resource_name")
    event = payload.get("event_type")
    resource_id = payload.get("resource_id")
    project_id = payload.get("project_id")
    company_id = os.getenv("PROCORE_COMPANY_ID")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    base = os.getenv("PROCORE_BASE_URL")
    db = get_db()
    cur = db.cursor()

    if resource == "Project" and event == "create":
        r = httpx.get(f"{base}/rest/v1.0/projects/{resource_id}",
            headers=headers, params={"company_id": company_id})
        p = r.json()
        cur.execute("""
            INSERT INTO projects (id, name, status, created_at)
            VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
        """, (p["id"], p["name"], p.get("status"), p.get("created_at")))

    elif resource == "Submittal" and event == "create":
        r = httpx.get(f"{base}/rest/v1.0/projects/{project_id}/submittals/{resource_id}",
            headers=headers)
        s = r.json()
        cur.execute("""
            INSERT INTO submittals (id, project_id, title, status,
            responsible_contractor, received_date, returned_date,
            on_site_date, revision_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING
        """, (
            s["id"], project_id, s.get("title"), s.get("status"),
            s.get("responsible_contractor", {}).get("name") if s.get("responsible_contractor") else None,
            s.get("received_date"), s.get("returned_date"),
            s.get("on_site_date"), s.get("number_of_revisions", 0)
        ))

    db.commit()
    cur.close()
    db.close()
    return {"status": "ok"}

# Saare projects dikhao
@app.get("/projects")
def get_projects():
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM projects ORDER BY synced_at DESC")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows

# Ek project ke saare submittals
@app.get("/projects/{project_id}/submittals")
def get_submittals(project_id: int):
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM submittals WHERE project_id = %s", (project_id,))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows

# Analytics
@app.get("/analytics/submittals/{project_id}")
def get_analytics(project_id: int):
    db = get_db()
    cur = db.cursor()
    today = date.today()
    in_14_days = today + timedelta(days=14)

    cur.execute("SELECT COUNT(*) FROM submittals WHERE project_id=%s AND status!='approved' AND on_site_date<%s", (project_id, today))
    overdue = cur.fetchone()[0]

    cur.execute("SELECT AVG(returned_date - received_date) FROM submittals WHERE project_id=%s AND returned_date IS NOT NULL", (project_id,))
    avg_days = cur.fetchone()[0]

    cur.execute("SELECT responsible_contractor, COUNT(*) FROM submittals WHERE project_id=%s AND status='open' GROUP BY responsible_contractor", (project_id,))
    by_contractor = dict(cur.fetchall())

    cur.execute("SELECT COUNT(*) FROM submittals WHERE project_id=%s AND status!='approved' AND on_site_date BETWEEN %s AND %s", (project_id, today, in_14_days))
    urgent = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FILTER (WHERE revision_count>0)*100.0/NULLIF(COUNT(*),0) FROM submittals WHERE project_id=%s", (project_id,))
    pct_revised = cur.fetchone()[0]

    cur.execute("SELECT status, COUNT(*) FROM submittals WHERE project_id=%s GROUP BY status", (project_id,))
    status_counts = dict(cur.fetchall())

    cur.close()
    db.close()

    return {
        "overdue_not_approved": overdue,
        "avg_days_received_to_returned": float(avg_days) if avg_days else 0,
        "open_by_contractor": by_contractor,
        "urgent_not_approved_within_14_days": urgent,
        "pct_submittals_with_revision": float(pct_revised) if pct_revised else 0,
        "status_counts": status_counts
    }
