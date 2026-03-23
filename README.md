# Municipal Federated Data Hub — Demo

## Contributor: Team "Champion"
  
This repository is a **hackathon prototype** of a federated municipal data exchange: a single gateway and UI sit on top of **three departmental data sources** (implemented here as CSV “legacy exports”), not a monolithic warehouse of sensitive records.

**Hackathon pitch deck / judge handout:** [docs/HACKATHON_PRESENTATION.md](docs/HACKATHON_PRESENTATION.md) — slide-style sections, live demo script, and a requirements traceability table.

---

## Quick start

1. **Python 3.10+** recommended.

2. Create a virtual environment and install dependencies (from the repo root):

   ```bash
   cd /path/to/hackthon2
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. **Run the server:**

   ```bash
   ./run_demo.sh
   ```

   Or manually:

   ```bash
   export PYTHONPATH="$(pwd)/backend"
   .venv/bin/uvicorn municipal_hub.main:app --host 0.0.0.0 --port 8080
   ```

4. **Open the site:** [http://localhost:8080](http://localhost:8080)

5. **Other pages:**
   - [http://localhost:8080/visibility.html](http://localhost:8080/visibility.html) — pick a **CSV**, list **every column**, then pick a **role**; exposed columns render **darker**, withheld columns **lighter**.
   - [http://localhost:8080/data-admin.html](http://localhost:8080/data-admin.html) — **role-gated CSV uploads** with **quality gates** and backups.

6. **Interactive API:** [http://localhost:8080/docs](http://localhost:8080/docs)

7. **Production note:** Set `MUNI_HUB_JWT_SECRET` to a long random string if the server is reachable from untrusted networks. The default secret is only for local demos.

---

## How to operate the website

The UI is a **single analyst dashboard** plus two supporting pages. Access rules are simulated with **JWT department roles** (not separate SSO integrations).

### Main dashboard (`/`)

1. **Choose a department role** in **Identity (JWT)**:
   - **public** — anonymous / citizen-style tier (same as having no token).
   - **dept_public_health** — Public Health department viewer.
   - **dept_engineering** — Engineering department viewer.
   - **dept_planning** — Planning department viewer.

2. Click **Issue demo token**. The token is stored in **browser localStorage** as `Authorization: Bearer …` on API calls.

3. Set **Federated query** filters (disease substring, year, row cap) and click **Load federated layers**.

4. **Map legend:** pink = medical, green = infra/drainage, yellow = planning applications. **Public** users get **no health markers** (no coordinates at that tier); use **Federated JSON** to compare payloads anyway.

5. **Federated JSON — Show / hide JSON** toggles the **full last `/api/v1/federated/scenario` response** in the sidebar. Use this to **diff visibility** between the three department tokens without clicking every marker.

6. **Data catalog** and **Audit log** behave as before (audit is **in-memory** and resets on server restart).

### Field visibility page (`/visibility.html`)

1. Open it **via the running app** (e.g. `http://localhost:8080/visibility.html`). Opening the HTML file directly from disk (`file://`) will leave the page empty because the browser cannot reach the API.
2. **Data file** — choose one of the three departmental extracts. The UI lists **all columns** read from the actual CSV header (`pandas.read_csv(..., nrows=0)`).
3. **Viewer role** — choose `public`, `dept_public_health`, `dept_engineering`, or `dept_planning`. Each row gets a **visibility token** (`visible`, `redacted`, `aggregate_only`, `hidden`) and a CSS emphasis level: **strong** (darkest) for fully exposed, **mid** for partial/aggregate/redacted, **faint** (lightest) for hidden.

Rules are implemented in `backend/municipal_hub/visibility_matrix.py` (per-column functions). Tune them when `data_service.py` federation rules change.

### JWT role body (`POST /api/v1/auth/token`)

- Request body uses a **string** `role` (not a strict OpenAPI enum) so older tooling or cached `/docs` schemas cannot block values like `dept_public_health`.
- Allowed values: `public`, `dept_public_health`, `dept_engineering`, `dept_planning`.
- **Legacy aliases** still work: `planner` → `dept_planning`, `health_official` → `dept_public_health`.
- After pulling code changes, **restart Uvicorn** so the running process matches the repo.

### Data admin page (`/data-admin.html`)

1. Issue the correct **department token** on the main dashboard (or reuse localStorage).
2. Choose a CSV and click **Upload & validate**.
3. **403** if the JWT role does not own that dataset. **422** if **quality checks** fail (errors appear in the response body and in the **audit log**).
4. On success, the file replaces the on-disk extract under `data/` and a **timestamped copy** is saved under `data/backups/`. In-memory CSV caches are **cleared** automatically (no restart needed for uploads).

---

## Data quality, audit, and temporal consistency (demo)

Aligned with the hackathon narrative (QA before exchange, audit for trust, time metadata):

| Pillar | Implementation |
|--------|------------------|
| **Quality gates** | `upload_quality.py` runs **before** a file replaces `data/*.csv`. Health: required columns, year range `[1990, 2035]`, non-negative `WR Count`, **rejects** impossible `WR Crude Rate per 100000` **> 100,000**. Drainage / planning have structural checks and sanity warnings (e.g. UTM envelope). |
| **Quality metadata** | Successful validations return `quality_score`, `status` (`approved` / `provisional`), `record_time`, and notes on **observation vs record** granularity. |
| **Audit** | Accept/reject uploads are logged with role and summary. Existing catalog/scenario/audit reads remain audited. |
| **Temporal hints** | Unified events include `observation_time` / `record_time` strings where relevant; `scenario_bundle` exposes a small **lineage** block listing source filenames and join logic. |

This is **not** Great Expectations, Iceberg time-travel, or OpenLineage — it is a **credible stub** you can narrate as the first increment toward those systems.

---

## Why this satisfies privacy constraints (demo scope)

| Constraint | How the demo addresses it |
|------------|---------------------------|
| **No individual health PII in open inputs** | Surveillance CSV is **aggregate**; no patient identifiers are loaded. |
| **Purpose limitation / least privilege** | **Three department JWTs** each receive **different slices** of the same federated response (see federated tables + `/visibility.html` column rules below). |
| **Health spatial disclosure** | **public:** no `geojson` on medical events. **Department roles:** community **centroids** only (demo keying), not residences. |
| **Drainage linkage** | Only **`dept_public_health`** receives `linked_drainage_area_id` / `linked_drainage_label` on medical events — supports environmental-health narrative without giving every peer engineering internals on health objects. |
| **Planning PII** | **public:** redacted address & applicant. **dept_public_health** / **dept_engineering:** address visible, applicant **redacted**, **no** contacts. **dept_planning:** full applicant + **contact_email** / **contact_phone**. |
| **Engineering internals** | **`level_name`** and **`maintenance_recent`** appear for **dept_engineering** and **dept_public_health** (peer ops). **dept_planning** and **public** get **summary** infra payloads only. |
| **Federation** | Responses are **merged views** with **RBAC field filtering**, not a raw dump of all three silos to everyone. |

---

## How to manage the “data lake” in this project

### Files on disk

| Path | Role |
|------|------|
| `data/Annual_Infectious_Disease_Data_Disease_Year_Sex.CSV` | Public health aggregate export |
| `data/Sanitary_Drainage_Areas_-8763139708202360098.csv` | Engineering drainage table |
| `data/Planning_Applications_Active.csv` | Planning applications |

### Three ways to refresh data

1. **Web upload (preferred in demo)** — `data-admin.html` + matching JWT; passes QA; writes file + backup; **clears caches**.
2. **Manual copy** — Drop a new CSV into `data/` with the same filename, then **restart Uvicorn** (manual edits do not clear `@lru_cache` unless you restart).
3. **Catalog-only changes** — Edit `backend/municipal_hub/catalog.py` for metadata; no data movement.

`data/backups/` is listed in `.gitignore` so large backup CSVs do not clutter git.

---

## What each department sees (JWT roles)

Same SPA; **switch token** to compare. The **Federated JSON** panel is the fastest way to see differences side-by-side.

### Public Health — `dept_public_health`

| Layer | What you get |
|-------|----------------|
| **Medical** | Community centroid + **`linked_drainage_area_id`** / **`linked_drainage_label`** (environmental-health demo). |
| **Infra** | Full detail: `level_name`, `maintenance_recent`, WQI. |
| **Planning** | Address + land use + status; **applicant redacted**; **no** contact fields. |

### Engineering — `dept_engineering`

| Layer | What you get |
|-------|----------------|
| **Medical** | Centroid + counts/rates; **no** drainage linkage on health events. |
| **Infra** | Full internal fields (your dataset). |
| **Planning** | Address visible; applicant **redacted**; **no** contacts. |

### Planning — `dept_planning`

| Layer | What you get |
|-------|----------------|
| **Medical** | Centroid + counts/rates; **no** drainage linkage. |
| **Infra** | **Summary only** (ID + WQI + `status: summary_only`) — no `level_name`. |
| **Planning** | **Full** applicant + **contact_email** / **contact_phone** (your departmental records). |

### Public — `public` (or no token)

| Layer | What you get |
|-------|----------------|
| **Medical** | Metrics only, **no map geometry**. |
| **Infra** | Summary payload (no hierarchy names). |
| **Planning** | Redacted address & applicant. |

---

## API cheat sheet

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/auth/token` | JSON body: `role` is a **string** (see above). Example: `{"role":"dept_engineering","sub":"analyst"}`. |
| `GET` | `/api/v1/catalog` | Data catalog entries. |
| `GET` | `/api/v1/governance/field-visibility` | JSON: `roles` + `datasets[]` with every CSV column and `by_role` visibility map for `/visibility.html`. |
| `GET` | `/api/v1/federated/scenario` | Query: `disease`, `year`, `limit`. Federated layers + lineage hints. |
| `GET` | `/api/v1/governance/audit` | Recent audit entries. |
| `POST` | `/api/v1/data/upload/health` | `multipart/form-data` file; requires **`dept_public_health`**. |
| `POST` | `/api/v1/data/upload/drainage` | Requires **`dept_engineering`**. |
| `POST` | `/api/v1/data/upload/planning` | Requires **`dept_planning`**. |
| `GET` | `/api/v1/internal/adapters/health/raw` | Tiny CSV preview. |

---

## Repository layout

```
hackthon2/
├── data/                           # CSV extracts (+ backups/ created on upload)
├── backend/municipal_hub/
│   ├── main.py                     # FastAPI routes (uploads, visibility API)
│   ├── data_service.py             # Adapters, RBAC transforms, file replace + cache clear
│   ├── visibility_matrix.py      # CSV column discovery + per-role visibility rules
│   ├── upload_quality.py         # Pre-ingest validation & quality metadata
│   ├── auth.py, catalog.py, audit.py, schema.py
├── web/
│   ├── index.html                  # Map dashboard
│   ├── visibility.html             # File + role column highlighter
│   ├── data-admin.html             # QA uploads
│   └── assets/                     # styles, app.js, visibility.js, admin.js
├── requirements.txt
├── run_demo.sh
└── README.md
```
