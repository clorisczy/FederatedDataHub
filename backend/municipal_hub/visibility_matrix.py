"""Per-column visibility for each departmental CSV (hub / federation view)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

ROLE_KEYS = ["public", "dept_public_health", "dept_engineering", "dept_planning"]

ROLE_LABELS: list[dict[str, str]] = [
    {"key": "public", "label": "Public (no dept JWT)"},
    {"key": "dept_public_health", "label": "Public Health dept"},
    {"key": "dept_engineering", "label": "Engineering dept"},
    {"key": "dept_planning", "label": "Planning dept"},
]

DATASETS: list[dict[str, str]] = [
    {
        "file_id": "health_surveillance",
        "file_name": "Annual_Infectious_Disease_Data_Disease_Year_Sex.CSV",
        "department": "Public Health",
        "path": str(DATA_DIR / "Annual_Infectious_Disease_Data_Disease_Year_Sex.CSV"),
    },
    {
        "file_id": "sanitary_drainage",
        "file_name": "Sanitary_Drainage_Areas_-8763139708202360098.csv",
        "department": "Engineering",
        "path": str(DATA_DIR / "Sanitary_Drainage_Areas_-8763139708202360098.csv"),
    },
    {
        "file_id": "planning_applications",
        "file_name": "Planning_Applications_Active.csv",
        "department": "Planning",
        "path": str(DATA_DIR / "Planning_Applications_Active.csv"),
    },
]


def _strip_col(name: str) -> str:
    return str(name).strip().lstrip("\ufeff")


def _load_csv_columns(path: Path) -> list[str]:
    df = pd.read_csv(path, nrows=0)
    return [_strip_col(c) for c in df.columns]


def _all_same(level: str) -> dict[str, str]:
    return {k: level for k in ROLE_KEYS}


def _health_column_vis(column: str) -> dict[str, str]:
    c = _strip_col(column)
    # Not surfaced in demo UnifiedEvent payloads — still “in file” but not exposed through hub.
    if c.startswith("ON ") or c in (
        "WR 5 Year Average Rate",
        "ON Crude Rate per 100000",
        "ON 5 Year Average Rate",
    ):
        return _all_same("hidden")
    if c in ("Year", "Disease", "Gender"):
        out = _all_same("visible")
        out["public"] = "aggregate_only"
        return out
    if c in ("WR Count", "WR Crude Rate per 100000"):
        return _all_same("visible")
    return _all_same("visible")


def _drainage_column_vis(column: str) -> dict[str, str]:
    c = _strip_col(column)
    if c == "SANDRAINAGEAREAID":
        return _all_same("visible")
    if c in ("STATUS", "CATEGORY", "SUBCATEGORY"):
        return _all_same("visible")
    out = {
        "public": "hidden",
        "dept_planning": "hidden",
        "dept_public_health": "visible",
        "dept_engineering": "visible",
    }
    return out


def _planning_column_vis(column: str) -> dict[str, str]:
    n = _strip_col(column)
    u = n.upper()

    if u in (
        "X",
        "Y",
        "OBJECTID",
        "PLANNINGCOMMUNITYID",
        "WARDID",
        "NEIGHBOURHOOD_ASSOCIATIONID",
        "APPLICATION_NO",
        "STATUS",
        "GLOBALID",
        "SORTID",
        "PARCELID",
        "PROPERTY_UNIT",
        "FOLDERRSN",
        "FOLDERYEAR",
        "FOLDERNAME",
        "FOLDERTYPE",
        "SUBTYPE",
        "PRIMARY_PROPERTY",
        "COMBINED_APPLICATION",
        "INDATE",
        "PUBLIC_STATUS_UPDATE",
        "AMANDA_STATUS_DESC",
        "PROP_MAX_RES_UNITS_INCIR",
        "PROP_MAX_RES_UNITS_DA",
        "PROPOSED_COMMERCIAL_HA",
        "PROPOSED_INSTITUTIONAL_HA",
        "PROPOSED_PARKLAND_HA",
        "PROP_SIZE_HA",
        "EXISTING_OPA_LANDUSE",
        "PROPOSED_OPA_LANDUSE",
        "EXISTING_ZONING",
        "PROPOSED_ZONING",
        "EXISTING_LANDUSE",
        "PROPOSED_LANDUSE",
    ):
        return _all_same("visible")

    if u == "ADDRESS":
        return {
            "public": "redacted",
            "dept_public_health": "visible",
            "dept_engineering": "visible",
            "dept_planning": "visible",
        }

    if u in ("APPLICANT", "PROPERTY_OWNER"):
        return {
            "public": "redacted",
            "dept_public_health": "redacted",
            "dept_engineering": "redacted",
            "dept_planning": "visible",
        }

    if u.startswith("CONTACT_") or u in ("CONTACT_EMAIL", "CONTACT_PHONE", "CONTACT_TTY"):
        return {
            "public": "hidden",
            "dept_public_health": "hidden",
            "dept_engineering": "hidden",
            "dept_planning": "visible",
        }

    if (
        "IMAGE_" in u
        or "THUMBNAIL" in u
        or u.endswith("_LINK")
        or "DOCUMENT" in u
        or u == "DESCRIPTION"
        or u == "ISSUED_BY"
        or "MEETING" in u
        or u.endswith("_DATE")
        or u == "HIGHLIGHT_APP"
        or u == "PUBLIC_STATUS_DESC"
    ):
        return {
            "public": "hidden",
            "dept_public_health": "visible",
            "dept_engineering": "visible",
            "dept_planning": "visible",
        }

    return _all_same("visible")


def _column_vis_for(file_id: str, column: str) -> dict[str, str]:
    if file_id == "health_surveillance":
        return _health_column_vis(column)
    if file_id == "sanitary_drainage":
        return _drainage_column_vis(column)
    if file_id == "planning_applications":
        return _planning_column_vis(column)
    return _all_same("hidden")


def build_dataset_column_payload(ds: dict[str, str]) -> dict:
    path = Path(ds["path"])
    if not path.is_file():
        columns: list[str] = []
    else:
        columns = _load_csv_columns(path)
    rows = []
    for col in columns:
        rows.append({"name": col, "by_role": _column_vis_for(ds["file_id"], col)})
    return {
        "file_id": ds["file_id"],
        "file_name": ds["file_name"],
        "department": ds["department"],
        "columns": rows,
    }


def visibility_payload() -> dict:
    """Used by /visibility.html — every CSV column with per-role visibility tokens."""
    return {
        "roles": ROLE_LABELS,
        "datasets": [build_dataset_column_payload(ds) for ds in DATASETS],
    }
