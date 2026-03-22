from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from municipal_hub import audit, catalog, data_service, visibility_matrix
from municipal_hub.auth import (
    create_access_token,
    get_current_principal,
    parse_token_role_string,
    role_from_principal,
)
from municipal_hub.data_service import DRAINAGE_CSV, HEALTH_CSV, PLANNING_CSV
from municipal_hub.schema import CatalogEntry, Role, TokenRequest
from municipal_hub.upload_quality import (
    validate_drainage_csv,
    validate_health_csv,
    validate_planning_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

app = FastAPI(
    title="Municipal Federated Data Hub",
    description="Hackathon demo: catalog + department RBAC + QA uploads + field visibility.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/auth/token")
def issue_token(body: TokenRequest) -> dict:
    role = parse_token_role_string(body.role)
    token = create_access_token(sub=body.sub, role=role)
    audit.record(
        role=role.value,
        action="token_issued",
        resource="auth",
        detail=body.sub,
    )
    return {"access_token": token, "token_type": "bearer", "role": role.value}


@app.get("/api/v1/catalog", response_model=list[CatalogEntry])
def get_catalog(principal: dict = Depends(get_current_principal)) -> list[CatalogEntry]:
    r = role_from_principal(principal)
    audit.record(role=r.value, action="read", resource="catalog")
    return catalog.CATALOG


@app.get("/api/v1/governance/field-visibility")
def field_visibility(principal: dict = Depends(get_current_principal)) -> dict:
    r = role_from_principal(principal)
    audit.record(role=r.value, action="read", resource="field_visibility_matrix")
    return visibility_matrix.visibility_payload()


@app.get("/api/v1/federated/scenario")
def federated_scenario(
    disease: str | None = None,
    year: int | None = None,
    limit: int = 25,
    principal: dict = Depends(get_current_principal),
) -> dict:
    r = role_from_principal(principal)
    audit.record(
        role=r.value,
        action="federated_query",
        resource="scenario",
        detail=f"disease={disease},year={year}",
    )
    bundle = data_service.scenario_bundle(
        role=r,
        disease=disease,
        year=year,
        per_source_limit=max(1, min(limit, 80)),
    )
    bundle["effective_role"] = r.value
    return bundle


@app.get("/api/v1/governance/audit")
def governance_audit(principal: dict = Depends(get_current_principal)) -> dict:
    r = role_from_principal(principal)
    audit.record(role=r.value, action="read", resource="audit_log")
    return {"entries": [e.model_dump() for e in audit.recent(40)]}


@app.get("/api/v1/internal/adapters/health/raw")
def raw_health_preview(principal: dict = Depends(get_current_principal)) -> dict:
    r = role_from_principal(principal)
    audit.record(role=r.value, action="adapter_peek", resource="health_raw")
    return data_service.health_raw_preview_rows(5)


def _ensure_upload_role(principal: dict, allowed: Role) -> Role:
    r = role_from_principal(principal)
    if r != allowed:
        raise HTTPException(
            status_code=403,
            detail=f"This upload requires role {allowed.value}; current role is {r.value}.",
        )
    return r


@app.post("/api/v1/data/upload/health")
async def upload_health(
    file: UploadFile = File(...),
    principal: dict = Depends(get_current_principal),
) -> dict:
    r = _ensure_upload_role(principal, Role.DEPT_PUBLIC_HEALTH)
    content = await file.read()
    report = validate_health_csv(content)
    if not report["ok"]:
        audit.record(
            role=r.value,
            action="upload_rejected",
            resource="health_csv",
            detail="; ".join(report["errors"]),
        )
        raise HTTPException(status_code=422, detail=report)
    data_service.replace_dataset_file(target=HEALTH_CSV, content=content)
    audit.record(
        role=r.value,
        action="upload_accepted",
        resource="health_csv",
        detail=f"quality={report['quality']}",
    )
    return {"stored": True, "path": str(HEALTH_CSV), "validation": report}


@app.post("/api/v1/data/upload/drainage")
async def upload_drainage(
    file: UploadFile = File(...),
    principal: dict = Depends(get_current_principal),
) -> dict:
    r = _ensure_upload_role(principal, Role.DEPT_ENGINEERING)
    content = await file.read()
    report = validate_drainage_csv(content)
    if not report["ok"]:
        audit.record(
            role=r.value,
            action="upload_rejected",
            resource="drainage_csv",
            detail="; ".join(report["errors"]),
        )
        raise HTTPException(status_code=422, detail=report)
    data_service.replace_dataset_file(target=DRAINAGE_CSV, content=content)
    audit.record(
        role=r.value,
        action="upload_accepted",
        resource="drainage_csv",
        detail=f"quality={report['quality']}",
    )
    return {"stored": True, "path": str(DRAINAGE_CSV), "validation": report}


@app.post("/api/v1/data/upload/planning")
async def upload_planning(
    file: UploadFile = File(...),
    principal: dict = Depends(get_current_principal),
) -> dict:
    r = _ensure_upload_role(principal, Role.DEPT_PLANNING)
    content = await file.read()
    report = validate_planning_csv(content)
    if not report["ok"]:
        audit.record(
            role=r.value,
            action="upload_rejected",
            resource="planning_csv",
            detail="; ".join(report["errors"]),
        )
        raise HTTPException(status_code=422, detail=report)
    data_service.replace_dataset_file(target=PLANNING_CSV, content=content)
    audit.record(
        role=r.value,
        action="upload_accepted",
        resource="planning_csv",
        detail=f"quality={report['quality']}",
    )
    return {"stored": True, "path": str(PLANNING_CSV), "validation": report}


@app.get("/")
def spa_index():
    index = WEB_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "Place web/index.html or open /docs"}


@app.get("/visibility.html")
def visibility_page():
    p = WEB_DIR / "visibility.html"
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/data-admin.html")
def data_admin_page():
    p = WEB_DIR / "data-admin.html"
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


if WEB_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
