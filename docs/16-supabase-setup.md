# Supabase Setup (and Render Deployment)

Step-by-step guide for hosting the WaitLess backend on **Render** with the
database on **Supabase**.

> **Key concept:** In this project Supabase is used purely as a *managed
> PostgreSQL server*. The application keeps its own JWT authentication
> (`app.core.security`), so Supabase Auth, the Supabase client SDK and the
> PostgREST data API are **not** used. The backend talks plain SQL through
> SQLAlchemy + Alembic.

---

## 1. Create the Supabase project

1. Sign in at <https://supabase.com/dashboard>.
2. Click **New project**.
3. Fill in:
   - **Name**: `waitless`
   - **Database password**: choose a strong password and **save it somewhere
     safe**. The password is never shown again in plain text.
     - Tip: use only letters and digits (for example `WaitLess2026Db`).
       Special characters such as `#`, `@`, `?` and `:` must be URL-encoded
       when embedded in a connection string, which is an easy source of
       broken deployments.
   - **Region**: pick the region closest to your Render region. Render's
     default region is Oregon (`us-west-1`). Supabase regions look like
     `us-east-1`, `us-west-1`, `eu-central-1`.
   - **Plan**: Free is enough to start.
4. Wait ~2 minutes while the database provisions.

After creation you need three values. They are all visible in
**Project Settings → General** and **Project Settings → Database**:

| Value | Where to find it | Example |
|---|---|---|
| Project ref | Project URL: `supabase.com/dashboard/project/<ref>` | `abcdefghijklmnop` |
| Region | Project Settings → Database | `us-east-1` |
| DB password | The one you set in step 3 | `WaitLess2026Db` |

---

## 2. Get the correct connection string

Go to **Project Settings → Database → Connection string** and switch the
driver tabs to **URI**.

You will see three variants. Only one of them works from Render:

| Variant | Host | Port | Use it? |
|---|---|---|---|
| **Direct connection** | `db.<ref>.supabase.co` | 5432 | **No** — IPv6 only, Render cannot reach it |
| **Session pooler** | `aws-0-<region>.pooler.supabase.com` | 5432 | **Yes** — IPv4, safest for Alembic + app |
| **Transaction pooler** | `aws-0-<region>.pooler.supabase.com` | 6543 | Works, but breaks session state |

**Use the session pooler (port 5432).**

Reason: Render instances have no IPv6 egress, and Supabase's *direct*
connection host resolves to IPv6-only addresses. The session pooler is
IPv4-reachable and behaves like a normal PostgreSQL server, which is exactly
what SQLAlchemy and Alembic expect.

The final URL looks like:

```text
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

Notes:

- The username is `postgres.<ref>` (with a dot), not plain `postgres`.
- The database name is `postgres`.
- `?sslmode=require` is mandatory — Supabase terminates TLS at the pooler.
- **Port 5432 (session mode) is required, not 6543 (transaction mode).** The
  application uses psycopg 3, which uses server-side prepared statements.
  Transaction-mode pooling breaks those, so the connection must be pinned to
  one backend session for its whole lifetime.

If your password contains special characters, URL-encode it
(`#` → `%23`, `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `?` → `%3F`).
In PowerShell:

```powershell
[System.Web.HttpUtility]::UrlEncode("My:Pass#word")
```

---

## 3. Lock down the data API

Supabase automatically exposes every table in the `public` schema through a
public REST endpoint (`https://<ref>.supabase.co/rest/v1/<table>`) for the
`anon` role. The WaitLess tables are created by Alembic, not by the Supabase
dashboard, so Row Level Security is **not** enabled on them — which would
mean anyone with your project ref could read the tables.

Fix this in the **SQL Editor** (left sidebar) — run once, after the schema
exists:

```sql
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
```

Optionally also turn the Data API off entirely:
**Project Settings → API → Data API → Disable**.

The backend connects as `postgres`, which bypasses RLS, so the application
keeps working either way.

---

## 4. Apply the schema from your machine

The application never creates tables itself — Alembic owns the schema.

From the `backend/` directory, point `DATABASE_URL` at the pooler and run the
migrations:

```powershell
cd backend
$env:DATABASE_URL = "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require"
$env:ENVIRONMENT = "development"
..\WaitLessVenv\Scripts\python.exe -m alembic upgrade head
```

Verify:

```powershell
..\WaitLessVenv\Scripts\python.exe -m alembic current
```

> **Note:** the migration `d9999999d001_add_additional_indexes.py` is currently
> **deleted** in the working tree, so `head` is `c0b015690a56` and the extra
> indexes are *not* applied. Restore it with
> `git checkout -- backend/alembic/versions/d9999999d001_add_additional_indexes.py`
> if the indexes are wanted.

Then verify the app can talk to Supabase:

```powershell
$env:ENVIRONMENT = "development"
..\WaitLessVenv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
# -> {"status":"ok"}
```

---

## 5. Configure Render

### 5.1 Create the web service

1. <https://dashboard.render.com> → **New** → **Web Service** → connect your
   Git repository.
2. **Root Directory**: `backend`  ← important, your `app/` package lives there.
3. **Runtime**: Python
4. **Python Version**: `3.14` (Render supports 3.14.8; your local venv is
   3.14.7 and SQLAlchemy 2.1.3 requires Python 3.14).
5. **Build Command**:
   ```bash
   pip install -r requirements.txt
   ```
6. **Start Command**:
   ```bash
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
   `alembic upgrade head` is idempotent, so it is safe to run on every
   restart. It also means you do not need a paid plan for
   `preDeployCommand`.
7. **Health Check Path**: `/health`

### 5.2 Environment variables

Add these under **Environment → Environment Variables** (mark the secrets as
*Secret*):

| Key | Value | Secret |
|---|---|---|
| `DATABASE_URL` | the session-pooler URI from step 2 | yes |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` | yes |
| `ENVIRONMENT` | `production` | no |
| `DEBUG` | `False` | no |
| `ALGORITHM` | `HS256` | no |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | no |
| `PYTHON_VERSION` | `3.14` | no |

`ENVIRONMENT=production` activates the safety check in
`app/core/config.py` that refuses to boot with the placeholder
`SECRET_KEY`. The same check runs locally, so a bad value fails fast on the
first deploy instead of in production traffic.

### 5.3 Deploy

Click **Create Web Service** and watch the build log. When it finishes you
get a URL like `https://waitless.onrender.com`. Check it:

```bash
curl https://waitless.onrender.com/health
# {"status":"ok"}
```

---

## 6. Free-tier caveats

- The free web service **spins down after 15 minutes of inactivity** and
  takes ~30–60 s to wake up. Your Flutter app must tolerate a slow first
  request.
- Free instances have **no IPv6 egress** → this is exactly why the Supabase
  *session pooler* is mandatory.
- The free instance has 512 MB RAM, which is comfortable for this app.
- 750 instance hours per month.
- `DATABASE_URL` is read at import time, so changing it requires a restart
  (Render does this automatically on env changes).

---

## 7. Create the first MANAGEMENT account

`POST /api/v1/auth/register` always creates a `COMMUTER`, and
`POST /api/v1/auth/users` — the only endpoint that can create a staff
account — requires a `MANAGEMENT` token. The first `MANAGEMENT` user
therefore has to be created directly in the database.

From the `backend` directory:

```powershell
..\WaitLessVenv\Scripts\python.exe scripts/create_staff.py `
  --email "admin@example.com" `
  --password "YourStrongPassword!" `
  --role MANAGEMENT
```

To create the account on Supabase instead of the local database, pass the
pooler connection string explicitly:

```powershell
..\WaitLessVenv\Scripts\python.exe scripts/create_staff.py `
  --database-url "postgresql://postgres.REF:PASS@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require" `
  --email "admin@example.com" `
  --password "YourStrongPassword!" `
  --role MANAGEMENT
```

The script uses the same Argon2id hashing as the API, so the account can log
in through `POST /api/v1/auth/login` immediately. It refuses to modify an
existing account, so re-running it is safe.

Once you hold a `MANAGEMENT` token, every other staff account is created
through the API:

```bash
curl -X POST https://<your-url>/api/v1/auth/users \
  -H "Authorization: Bearer <management-token>" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Bus Driver","email":"driver@example.com","password":"Password123!","role":"OPERATOR"}'
```

---

## 8. Operational notes

- **Backups**: enable **Point-in-Time Recovery** on the Supabase project
  (paid) or schedule `pg_dump` from a cron job.
- **Migrations**: never edit an already-applied migration. Always add a new
  one, otherwise the deployed database and your local database drift apart.
- **Connection limits**: Supabase's pooler counts sessions. `DB_POOL_SIZE=5`
  and `DB_MAX_OVERFLOW=5` (see `app/core/config.py`) keep the app well under
  the limit. `pool_pre_ping` is enabled so that connections closed by the
  pooler are transparently replaced.
- **Tests**: keep running `pytest` against a **local** PostgreSQL server.
  Supabase does not permit `CREATE DATABASE`, which the test suite uses to
  create `waitless_test` automatically.

---

## 9. Checklist

- [ ] Supabase project created, password saved
- [ ] Session-pooler URI copied, password URL-encoded
- [ ] `REVOKE` statements executed in the SQL editor
- [ ] `alembic upgrade head` run against Supabase
- [ ] `alembic current` shows the expected revision
- [ ] `/health` returns `{"status":"ok"}` locally against Supabase
- [ ] Render web service created with root dir `backend`
- [ ] Environment variables set, `SECRET_KEY` unique, `ENVIRONMENT=production`
- [ ] Deploy succeeds and `/health` returns `{"status":"ok"}` on the public URL
- [ ] `POST /api/v1/auth/register` returns `201` on the public URL
- [ ] `POST /api/v1/auth/login` returns a JWT on the public URL
- [ ] First `MANAGEMENT` account created with `scripts/create_staff.py`
- [ ] `POST /api/v1/auth/users` creates an `OPERATOR` account
