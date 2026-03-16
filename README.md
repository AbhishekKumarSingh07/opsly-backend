# Opsly Backend

Production-grade FastAPI REST API for the Opsly field-service management platform.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.135 |
| Language | Python 3.12 |
| ORM | SQLAlchemy 2.0 (Declarative) |
| Database | PostgreSQL 16 |
| Cache / Token Blacklist | Redis 7 |
| Auth | JWT HS256 (python-jose) + bcrypt + HttpOnly refresh cookie |
| Migrations | Alembic |
| Task Scheduler | APScheduler (cron, Asia/Kolkata) |
| File Storage | MinIO (dev) / AWS S3 (prod) via boto3 |
| Rate Limiting | SlowAPI |
| Bulk Import | openpyxl (xlsx), csv, json |
| Testing | pytest + httpx TestClient |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
opsly-backend/
├── app/
│   ├── core/           # config, security, dependencies, middleware, exceptions, permissions
│   ├── db/             # engine, session, base, mixins, audit listeners
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic v2 request/response schemas
│   ├── repositories/   # data-access layer (no business logic)
│   ├── services/       # business logic (state machines, validations)
│   ├── routers/        # FastAPI route handlers (HTTP only)
│   ├── tasks/          # APScheduler background jobs
│   ├── utils/          # geo, pagination, idempotency, file upload
│   └── main.py         # application factory
├── alembic/            # migration environment + version scripts
├── scripts/
│   └── seed.py         # dev seed data (3 users)
├── tests/              # pytest test suite
├── Dockerfile          # multi-stage build (builder → runtime)
├── docker-compose.yml  # backend-only compose (postgres + redis + minio + app)
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Running the Full Stack (Recommended)

> The root `docker-compose.yml` at `/opsly/docker-compose.yml` runs both backend **and** frontend together. Use that for day-to-day development.

```bash
# From the repo root (/opsly)
docker compose up -d

# After code changes — rebuild images
docker compose up --build -d

# Seed the database with dev users
docker exec opsly-app-1 sh -c "cd /app && python scripts/seed.py"

# Stop everything
docker compose down

# Stop and wipe all data (fresh DB)
docker compose down -v
```

### URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| MinIO Console | http://localhost:9001 |

### Default Dev Credentials

| Role | Email | Password |
|---|---|---|
| Owner | `owner@opsly.local` | `owner@123` |
| Moderator | `mod@opsly.local` | `moderator@123` |
| Staff | `staff@opsly.local` | `staff@123` |

---

## Running Backend Only (Local Dev)

```bash
# 1. Create virtualenv
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your Postgres / Redis / MinIO credentials

# 4. Apply migrations
alembic upgrade head

# 5. Seed dev users
python scripts/seed.py

# 6. Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | JWT signing secret (min 32 chars) |
| `DATABASE_URL` | ✅ | — | PostgreSQL DSN `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | ✅ | — | Redis DSN `redis://localhost:6379/0` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ❌ | `7` | Refresh token lifetime |
| `AWS_ACCESS_KEY_ID` | ❌ | `minioadmin` | S3 / MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | ❌ | `minioadmin` | S3 / MinIO secret |
| `AWS_REGION` | ❌ | `us-east-1` | S3 region (use `us-east-1` for MinIO) |
| `AWS_S3_BUCKET` | ❌ | `opsly-uploads` | S3 / MinIO bucket name |
| `S3_ENDPOINT_URL` | ❌ | `http://localhost:9000` | MinIO URL; leave blank for real AWS S3 |
| `OFFICE_GPS_LAT` | ✅ | — | Office latitude for geofence |
| `OFFICE_GPS_LNG` | ✅ | — | Office longitude for geofence |
| `GEOFENCE_RADIUS_METERS` | ❌ | `100.0` | Attendance geofence radius in metres |
| `CORS_ORIGINS` | ❌ | `["*"]` | Allowed origins (JSON array) |

---

## Roles & Permissions

Centralised in `app/core/permissions.py` (`PermissionPolicy`).

| Action | Owner | Moderator | Staff / Technician |
|---|---|---|---|
| Create resources | ✅ | ✅ | ❌ |
| Update / Delete | ✅ | ❌ | ❌ |
| Create users | Any role | Staff only | ❌ |
| Manage users (edit, deactivate) | ✅ | ❌ | ❌ |
| Approve attendance | Anyone's | Staff only | ❌ |
| Bulk import | ✅ | ✅ | ❌ |

---

## API Reference

### Auth — `/api/v1/auth`
| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/login` | Email/password → JWT + cookie | — |
| POST | `/refresh` | Rotate access token via cookie | — |
| POST | `/logout` | Blacklist refresh token | ✅ |
| GET | `/me` | Current user profile | ✅ |
| POST | `/change-password` | Change own password (clears `must_change_password`) | ✅ |

### Users — `/api/v1/users`
| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/` | List all users | Owner / Moderator |
| POST | `/` | Create user (sets `must_change_password=true`) | Owner / Moderator |
| GET | `/{id}` | Get user detail | Owner / self |
| PATCH | `/{id}` | Update name / phone / active status | Owner |
| POST | `/{id}/reset-password` | Reset password (sets `must_change_password=true`) | Owner |

### Bulk Import — `/api/v1/imports`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/staff` | Import staff from xlsx/csv/json | Owner / Moderator |
| POST | `/inventory` | Import inventory from xlsx/csv/json | Owner / Moderator |
| GET | `/` | List import history | Owner / Moderator |
| GET | `/{id}` | Get import detail + row errors | Owner / Moderator |
| GET | `/templates/staff` | Download staff CSV template | Owner / Moderator |
| GET | `/templates/inventory` | Download inventory CSV template | Owner / Moderator |
| GET | `/format-reference` | Column spec JSON for UI | Owner / Moderator |

### Tickets — `/api/v1/tickets`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/` | Create ticket | Moderator+ |
| GET | `/` | List tickets (filterable) | All |
| GET | `/{id}` | Ticket detail | All |
| POST | `/{id}/assign` | Assign technician(s) | Moderator+ |
| PATCH | `/{id}/status` | Update status | All (valid transitions) |
| POST | `/{id}/photos` | Upload photo | All |

### Attendance — `/api/v1/attendance`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/punch-in` | GPS + liveness punch-in | Staff+ |
| POST | `/punch-out` | Record punch-out | Staff+ |
| GET | `/my` | My attendance history | Staff+ |
| GET | `/pending` | Pending approvals | Moderator+ |
| PATCH | `/{id}/approve` | Approve record | Moderator+ |
| PATCH | `/{id}/flag` | Flag record | Moderator+ |
| GET | `/all` | All records (date filter) | Owner |

### Inventory — `/api/v1/inventory`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/intake` | Register new item | Moderator+ |
| POST | `/checkout` | Check out to ticket | Moderator+ |
| POST | `/return` | Return item by barcode | Moderator+ |
| POST | `/install` | Record installation | Moderator+ |
| GET | `/` | List inventory | All |
| GET | `/{id}` | Item detail | All |

### Expenses — `/api/v1/expenses`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/` | Submit claim | Staff+ |
| GET | `/my` | My history | Staff+ |
| GET | `/pending` | Pending review | Moderator+ |
| PATCH | `/{id}/review` | Approve / reject | Moderator+ |

### Tenders — `/api/v1/tenders`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/` | Create tender | Owner |
| GET | `/` | List tenders | All |
| GET | `/{id}` | Tender detail | All |
| PATCH | `/{id}/status` | Status transition | Owner |
| POST | `/{id}/milestones` | Add milestone | Owner |
| POST | `/{id}/documents` | Upload document | Moderator+ |

### Dashboards — `/api/v1/dashboard`
| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/owner` | KPIs + attendance with approver info + recent tickets | Owner |
| GET | `/moderator` | Open tickets, pending approvals | Moderator+ |
| GET | `/staff` | My tasks, today's attendance | Staff+ |

### Misc
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/sync/batch` | Offline batch sync |
| POST | `/api/v1/uploads/photo` | Direct photo upload |
| GET | `/health` | DB + Redis health check |

---

## User Management

- Created users get `must_change_password = true` by default
- `created_by` UUID is recorded on every user
- Owner can create any role; Moderator can only create `staff`
- Password reset forces `must_change_password = true` on the target account
- `POST /auth/change-password` clears `must_change_password` once changed

---

## Attendance Approval Hierarchy

- **Owner** can approve/reject any user's attendance
- **Moderator** can only approve/reject **staff** attendance
- **No self-approval** — a user cannot approve their own record
- Approved records store `approved_by` UUID, approver name/role, and `approved_at`

---

## Bulk Import Details

### Supported Formats
- `.xlsx` — parsed with openpyxl
- `.csv` — parsed with csv.DictReader
- `.json` — array of objects

### Staff Columns
| Column | Required | Notes |
|---|---|---|
| name | ✅ | Full name |
| email | ✅ | Must be unique |
| phone | ❌ | |
| role | ❌ | Defaults to `staff`; moderators cannot create `owner`/`moderator` |
| password | ❌ | Auto-generated if omitted; user must change on first login |

### Inventory Columns
| Column | Required | Notes |
|---|---|---|
| name | ✅ | |
| category | ✅ | |
| quantity | ✅ | Integer |
| unit | ❌ | e.g. `pcs`, `kg` |
| barcode | ❌ | Must be unique |
| serial_number | ❌ | Must be unique |
| unit_cost | ❌ | Decimal |
| location | ❌ | |
| notes | ❌ | |

### Behaviour
- Partial imports supported — valid rows succeed even if some fail
- Row-level errors stored as JSONB in `bulk_import_logs.error_details`
- All imported staff get `must_change_password = true`

---

## Database Migrations

```bash
# Generate after model changes
alembic revision --autogenerate -m "describe_change"

# Apply all pending
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

---

## Background Jobs

| Job | Schedule (IST) | Description |
|---|---|---|
| AMC Checker | 06:00 daily | Auto-creates ticket for DG sets due within 7 days |
| Inventory Reconciler | 02:00 nightly | Alerts on items checked out > 48 hours |

---

## Running Tests

```bash
source venv/bin/activate
pytest -v
```

Tests use an in-memory SQLite database — no PostgreSQL or Redis required.

---

## Architecture Decisions

- **3-layer separation**: Routers → Services → Repositories. No DB queries in routers/services directly.
- **Soft deletes**: All user-facing models use `is_deleted` / `deleted_at`.
- **Immutable audit log**: Append-only, written by SQLAlchemy event listeners.
- **GPS geofencing**: Haversine validation on punch-in. Out-of-range records are auto-flagged, not rejected.
- **Idempotency**: State-mutating endpoints accept `Idempotency-Key` header (Redis, 24h TTL).
- **File security**: MIME detected from magic bytes, not `Content-Type`. Allowed: JPEG, PNG, PDF. 10 MB limit.
- **Token rotation**: Refresh tokens rotate on every `/auth/refresh`. Old tokens added to Redis blacklist.

---

## License

MIT — see [LICENSE](LICENSE).
