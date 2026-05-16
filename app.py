import os
from datetime import date, timedelta

import httpx
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv()

app = FastAPI()


def connect_db():
    return psycopg2.connect(
        os.getenv("DATABASE_URL")
    )


def get_access_token():

    payload = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("PROCORE_CLIENT_ID"),
        "client_secret": os.getenv("PROCORE_CLIENT_SECRET")
    }

    response = httpx.post(
        "https://login.procore.com/oauth/token",
        json=payload
    )

    return response.json()["access_token"]


@app.post("/webhooks/procore")
async def handle_procore_webhook(request: Request):

    data = await request.json()

    resource = data.get("resource_name")
    event = data.get("event_type")

    resource_id = data.get("resource_id")
    project_id = data.get("project_id")

    company_id = os.getenv("PROCORE_COMPANY_ID")
    base_url = os.getenv("PROCORE_BASE_URL")

    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = connect_db()
    cur = conn.cursor()

    try:

        if resource == "Project" and event == "create":

            response = httpx.get(
                f"{base_url}/rest/v1.0/projects/{resource_id}",
                headers=headers,
                params={"company_id": company_id}
            )

            project = response.json()

            cur.execute("""
                INSERT INTO projects
                (id,name,status,created_at)
                VALUES(%s,%s,%s,%s)
                ON CONFLICT(id) DO NOTHING
            """, (
                project["id"],
                project["name"],
                project.get("status"),
                project.get("created_at")
            ))

        elif resource == "Submittal" and event == "create":

            response = httpx.get(
                f"{base_url}/rest/v1.0/projects/{project_id}/submittals/{resource_id}",
                headers=headers
            )

            submittal = response.json()

            contractor = None

            if submittal.get("responsible_contractor"):
                contractor = submittal[
                    "responsible_contractor"
                ].get("name")

            cur.execute("""
                INSERT INTO submittals(
                    id,
                    project_id,
                    title,
                    status,
                    responsible_contractor,
                    received_date,
                    returned_date,
                    on_site_date,
                    revision_count
                )

                VALUES(
                    %s,%s,%s,%s,%s,
                    %s,%s,%s,%s
                )

                ON CONFLICT(id)
                DO NOTHING
            """, (

                submittal["id"],
                project_id,
                submittal.get("title"),
                submittal.get("status"),
                contractor,
                submittal.get("received_date"),
                submittal.get("returned_date"),
                submittal.get("on_site_date"),
                submittal.get("number_of_revisions",0)

            ))

        conn.commit()

    except Exception as e:

        print("Webhook error:", e)
        conn.rollback()

    finally:

        cur.close()
        conn.close()

    return {"status": "ok"}


@app.get("/projects")
def get_projects():

    conn = connect_db()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cur.execute("""
        SELECT *
        FROM projects
        ORDER BY synced_at DESC
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return data


@app.get("/projects/{project_id}/submittals")
def get_submittals(project_id: int):

    conn = connect_db()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cur.execute("""
        SELECT *
        FROM submittals
        WHERE project_id=%s
    """, (project_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


@app.get("/analytics/submittals/{project_id}")
def analytics(project_id: int):

    conn = connect_db()
    cur = conn.cursor()

    today = date.today()
    next_14 = today + timedelta(days=14)

    cur.execute("""
        SELECT COUNT(*)
        FROM submittals
        WHERE project_id=%s
        AND status!='approved'
        AND on_site_date<%s
    """, (project_id, today))

    overdue = cur.fetchone()[0]

    cur.execute("""
        SELECT AVG(returned_date-received_date)
        FROM submittals
        WHERE project_id=%s
        AND returned_date IS NOT NULL
    """, (project_id,))

    avg_days = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "overdue_not_approved": overdue,
        "avg_days_received_to_returned":
            float(avg_days) if avg_days else 0
    }
