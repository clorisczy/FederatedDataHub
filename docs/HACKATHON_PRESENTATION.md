# Municipal Federated Data Hub — Hackathon Demonstration Document

**Challenge alignment:** City municipal data infrastructure blueprint (Challenge #2 style): federated exchange, governance, privacy, cross-department value, and a working prototype.

**How to use this file**

- **As a slide deck:** Treat each top-level section (`##`) as one PowerPoint / Google Slides slide (or split long sections across two slides). Copy bullet points onto slides; add screenshots from the running app (`http://localhost:8080`).
- **As a judge handout:** Print or export this Markdown to PDF (VS Code, Pandoc, or GitHub preview).

**Repository:** FastAPI backend + static web UI + Region of Waterloo / Kitchener open-data style CSV extracts under `data/`.

---

## Slide 1 — Title

**Municipal Federated Data Hub**  
*Blueprint + prototype for safe, cross-department civic data sharing*

- **Deliverable types:** Architecture story • Governance rules • Working demo (map + APIs + QA uploads)
- **Demo stack:** Python (FastAPI), JWT RBAC, Leaflet map, CSV departmental “adapters”
- **Scenario:** Public health surveillance + sanitary drainage + planning applications — one federated view without a single raw-PII warehouse

---

## Slide 2 — The problem (hackathon pain points)

| Pain point | What cities face |
|------------|------------------|
| **Siloed departments** | Engineering, planning, and health each own legacy systems that do not interoperate. |
| **Reluctance to share** | Fear of privacy breach → default is “no share,” blocking joint response. |
| **Inconsistent standards** | Same concept (e.g. geography, time) represented differently per department. |
| **Invisible ROI** | “Data infrastructure” is hard to fund compared to visible capital projects. |

**Our thesis:** A **federated hub** with **clear governance** and **proven cross-use** (one map, one API contract) makes sharing **safer and measurable**, not “all data to everyone.”

---

## Slide 3 — What we built (capability summary)

1. **Federated gateway** — `GET /api/v1/federated/scenario` merges three departmental layers into one response (standardized JSON events), without requiring one central database of sensitive records.
2. **Department JWT roles** — `dept_public_health`, `dept_engineering`, `dept_planning`, plus `public`; each role receives **different fields and geometry** for the same logical datasets.
3. **Data catalog** — Discoverable dataset metadata (`GET /api/v1/catalog`): owner, purpose, cadence, common schema hooks.
4. **Field visibility UI** — `/visibility.html`: pick a CSV → list **every column** → pick a role → **darker = more exposed**, **lighter = withheld** through the hub.
5. **Quality gates + uploads** — `/data-admin.html` + `POST /api/v1/data/upload/*`: only the **owning department role** may replace its file; validation runs **before** ingest; backups to `data/backups/`.
6. **Audit trail** — Token issuance, catalog reads, federated queries, upload accept/reject logged (`GET /api/v1/governance/audit`).
7. **GIS** — Planning coordinates transformed from projected CRS (NAD83 UTM 17N) to WGS84 for the map; health uses **aggregate / community-level** linkage (demo), not street-level PII.

---

## Slide 4 — Architecture (blueprint)

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ Public Health   │   │ Engineering     │   │ Planning        │
│ (surveillance   │   │ (drainage CSV)   │   │ (applications   │
│  CSV export)    │   │                 │   │  CSV)           │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └──────────┬──────────┴──────────┬──────────┘
                    ▼
         ┌──────────────────────┐
         │  Adapter + transform │  ← RBAC, schema unify, PII rules
         │  (data_service.py)   │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │  API gateway         │  JWT, catalog, audit, federated
         │  (FastAPI)           │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │  Dashboard + pages    │  Map, JSON diff, visibility, admin
         └──────────────────────┘
```

**Principles:** *Logical* integration, *physical* distribution; legacy sources stay in place (CSV stands in for 20-year-old DB exports + future REST connectors).

---

## Slide 5 — Governance & privacy (how we satisfy “safe share”)

| Control | Implementation |
|--------|----------------|
| **Role-based access** | JWT carries `role`; adapters strip or enrich **spatial** and **PII** fields per role. |
| **Minimum necessary** | Example: only **Public Health** sees `linked_drainage_area_id` on medical events; Engineering does not get that cross-link on health payloads in this demo policy. |
| **Planning PII** | Address/applicant/contacts gated: **Planning dept** sees contacts; peers see redacted applicant; **public** sees redacted address. |
| **Health geography** | **Public:** no map geometry for health (regional aggregate only). **Departments:** community-centroid demo linkage — not home addresses. |
| **Transparency** | `/visibility.html` shows **per-column** policy for each CSV and role. |
| **Accountability** | Audit log records **who** (role) did **what** (query, upload, token). |

*Disclaimer:* Demo only — not a certified PHIPA/PIPEDA compliance system — but the **control pattern** matches what a real program would operationalize.

---

## Slide 6 — Unified interchange schema (standards story)

Events follow a small **common shape** (see API responses):

- `event_type`: `medical` | `infra` | `zone`
- `source_department`: provenance
- `temporal`: year / indate / synthetic windows + `observation_time` / `record_time` hints where applicable
- `spatial`: `location_key`, optional `geojson` Point, optional cross-domain keys (e.g. drainage link for health officials)
- `payload`: role-filtered business fields
- `access_level`, `pii_stripped`: explicit disclosure metadata

**Why it matters:** Departments keep internal formats; the **exchange layer** speaks one dialect (NGSI-LD–inspired / extensible to CityGML / NGSI-LD in production).

---

## Slide 7 — Use case: cross-department insight (story for judges)

**Narrative:** An analyst investigates **respiratory / environmental** patterns (demo: filter e.g. **Influenza**, **2024**).

- **Health layer:** Open aggregate counts positioned at **planning-community** centroids (deterministic demo keying — stands in for in-unit aggregation).
- **Engineering layer:** Sanitary drainage areas (synthetic map points where geometry is not in CSV — stands in for GIS service).
- **Planning layer:** Active applications with real projected coordinates → map.

**Value:** One pane ties **epidemiological signal**, **infrastructure context**, and **development pressure** — the kind of view silos prevent today.

---

## Slide 8 — Live demo script (3 minutes)

1. Run `./run_demo.sh` → open `http://localhost:8080`.
2. **Issue token** as `dept_public_health` → **Load federated layers** → show pink / green / yellow markers.
3. **Show / hide JSON** — point out `linked_drainage_area_id` on medical events.
4. Switch token to `dept_engineering` → reload → JSON shows **no** drainage link on health; infra still detailed.
5. Switch to `dept_planning` → planning contacts visible in payloads; infra **summary** only.
6. Open `/visibility.html` → select **Planning** file → switch **Public** vs **Planning** role → contrast row darkness.
7. Open `/data-admin.html` → attempt upload with **wrong** role (403) or **bad** health CSV e.g. crude rate &gt; 100k (422) → show **audit log** on main page.

---

## Slide 9 — Data quality, audit, temporal consistency

| Theme | What the prototype does |
|-------|-------------------------|
| **Quality before exchange** | `upload_quality.py`: schema checks, plausible years, non-negative counts, **reject impossible crude rates**; structural checks for drainage and planning. |
| **Quality metadata** | `quality_score`, `approved` / `provisional`, `record_time` returned on successful uploads. |
| **Audit** | Rejections and accepts logged with role and detail. |
| **Lineage** | `scenario_bundle` includes `lineage.sources` (filenames) and join narrative — extensible to OpenLineage / Marquez. |
| **Time** | Mixed cadence acknowledged (annual health vs. extract timestamps); fields document observation vs. record time where relevant. |

**Stretch goal named for roadmap:** Great Expectations, Iceberg/Delta time travel, streaming for alerts.

---

## Slide 10 — Incremental pathway (not big-bang)

1. **Pilot** — Two departments (e.g. health + engineering), one use case, read-only federation.
2. **Expand** — Add planning + formal DUA templates; persistent audit store; IdP instead of demo JWT.
3. **Harden** — Column-level policies in policy engine; automated lineage; formal anonymization k-anonymity for spatial releases.
4. **Scale** — Replace CSV with departmental APIs; regional data mesh; optional confidential computing for sensitive joins.

This matches the hackathon ask for a **practical, phased** municipal program.

---

## Slide 11 — Requirements traceability (hackathon criteria → evidence)

| Requirement / theme | Where this project demonstrates it |
|---------------------|--------------------------------------|
| **Blueprint + prototype** | Architecture slides + running FastAPI + 3 web surfaces |
| **Federated / non-monolithic hub** | Separate CSV sources; merged only at API; `lineage` in response |
| **Data catalog / discovery** | `GET /api/v1/catalog` + UI panel |
| **Governance (who sees what)** | JWT roles, `visibility_matrix.py`, `/visibility.html` |
| **Privacy & PII** | Redaction, no street-level health, drainage link only for health dept role |
| **RBAC** | Department tokens + upload enforcement + adapter logic |
| **Cross-department scenario** | Map + federated scenario (health + infra + planning) |
| **GIS** | Leaflet; CRS transform for planning X/Y |
| **Legacy compatibility** | CSV as stand-in for old exports; adapter pattern documented |
| **Data quality** | Upload validators + reject path + audit |
| **Audit / trust** | `governance/audit` + upload logging |
| **Standards-based exchange** | Unified event JSON; extensible to NGSI-LD / CityGML narrative |
| **Incremental rollout** | Slide 10 roadmap |

---

## Slide 12 — Tech stack & files (for technical judges)

| Layer | Technology / paths |
|-------|-------------------|
| API | FastAPI, `backend/municipal_hub/main.py` |
| Auth | JWT (`python-jose`), `auth.py` |
| Transforms | `data_service.py` |
| Visibility rules | `visibility_matrix.py` |
| QA | `upload_quality.py` |
| UI | `web/index.html`, `visibility.html`, `data-admin.html`, `web/assets/*.js` |
| Data | `data/*.csv` (open-data style samples) |

**API explorer:** `http://localhost:8080/docs`

---

## Slide 13 — Closing

**Takeaway:** We show that **cross-department value** and **privacy** can coexist when sharing is **governed**, **audited**, and **schema-first** — starting small with a **federated** model cities can actually adopt.

**Q&A prompts:**  
- How would this plug into ArcGIS REST / AMANDA APIs?  
- How would IdP and legal agreements replace demo JWT?  
- How would spatial statistics be certified for release (k-anonymity, differential privacy)?

---

### Appendix A — Export to PowerPoint (quick methods)

1. **Manual:** Create ~13 slides; paste each section’s bullets; add 4–6 screenshots.
2. **Google Slides import:** Paste Markdown into a converter or copy section by section.
3. **Pandoc** (if installed): `pandoc docs/HACKATHON_PRESENTATION.md -o deck.pptx` (layout may need cleanup).

### Appendix B — Suggested screenshots

1. Main map with three layers and legend.  
2. **Federated JSON** panel comparing two roles side by side (two browser windows).  
3. `/visibility.html` with strong vs faint rows.  
4. `/data-admin.html` after a failed validation (422 message).  
5. `/docs` OpenAPI page.  
6. Optional: simple diagram from Slide 4 recreated in PowerPoint SmartArt.
