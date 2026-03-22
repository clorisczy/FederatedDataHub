from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
from pyproj import Transformer

from municipal_hub.schema import Role, UnifiedEvent

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"

HEALTH_CSV = DATA_DIR / "Annual_Infectious_Disease_Data_Disease_Year_Sex.CSV"
DRAINAGE_CSV = DATA_DIR / "Sanitary_Drainage_Areas_-8763139708202360098.csv"
PLANNING_CSV = DATA_DIR / "Planning_Applications_Active.csv"

_transformer = Transformer.from_crs("EPSG:26917", "EPSG:4326", always_xy=True)


def clear_data_caches() -> None:
    _load_health_df.cache_clear()
    _load_drainage_df.cache_clear()
    _load_planning_df.cache_clear()
    planning_community_centroids.cache_clear()


def _h(*parts: str) -> int:
    s = "|".join(parts).encode()
    return int(hashlib.sha256(s).hexdigest()[:8], 16)


def _to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon, lat = _transformer.transform(float(x), float(y))
    return lon, lat


@lru_cache(maxsize=1)
def _load_health_df() -> pd.DataFrame:
    df = pd.read_csv(HEALTH_CSV)
    df.columns = [c.strip() for c in df.columns]
    return df


def health_raw_preview_rows(n: int = 5) -> dict:
    df = _load_health_df().head(n)
    return {"columns": list(df.columns), "rows": df.to_dict(orient="records")}


@lru_cache(maxsize=1)
def _load_drainage_df() -> pd.DataFrame:
    return pd.read_csv(DRAINAGE_CSV)


@lru_cache(maxsize=1)
def _load_planning_df() -> pd.DataFrame:
    return pd.read_csv(PLANNING_CSV)


@lru_cache(maxsize=1)
def planning_community_centroids() -> dict[int, dict]:
    df = _load_planning_df()
    out: dict[int, list[tuple[float, float]]] = {}
    for _, row in df.iterrows():
        try:
            pid = int(row["PLANNINGCOMMUNITYID"])
            lon, lat = _to_lonlat(row["X"], row["Y"])
        except (KeyError, TypeError, ValueError):
            continue
        out.setdefault(pid, []).append((lon, lat))
    centroids: dict[int, dict] = {}
    for pid, pts in out.items():
        av_lon = sum(p[0] for p in pts) / len(pts)
        av_lat = sum(p[1] for p in pts) / len(pts)
        centroids[pid] = {"lon": av_lon, "lat": av_lat, "n_applications": len(pts)}
    return centroids


def community_ids_ordered() -> list[int]:
    return sorted(planning_community_centroids().keys())


def pick_community_id(disease: str, year: int, gender: str) -> int:
    ids = community_ids_ordered()
    if not ids:
        return 0
    idx = _h(disease, str(year), gender) % len(ids)
    return ids[idx]


def pick_drainage_id(disease: str, year: int, gender: str) -> int:
    df = _load_drainage_df()
    ids = df["SANDRAINAGEAREAID"].dropna().astype(int).tolist()
    if not ids:
        return 0
    idx = _h(disease, str(year), gender, "drain") % len(ids)
    return int(ids[idx])


def _health_spatial_for_role(
    role: Role,
    *,
    pc_id: int,
    c: dict,
    drain_id: int,
    drain_lookup: pd.DataFrame,
) -> tuple[dict, str]:
    if role == Role.PUBLIC:
        return (
            {
                "location_key": "Region_of_Waterloo_Total",
                "geojson": None,
                "resolution": "regional_aggregate",
                "observation_time": "annual cohort (Year)",
                "record_time": "open_data_snapshot",
            },
            "L0_open_aggregate",
        )

    spatial_base = {
        "location_key": f"planning_community:{pc_id}",
        "geojson": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
        "resolution": "community_centroid",
        "observation_time": "annual cohort (Year)",
        "record_time": "open_data_snapshot",
    }

    if role == Role.DEPT_PUBLIC_HEALTH:
        try:
            drow = drain_lookup.loc[drain_id]
            level_name = str(drow.get("LEVEL_NAME", ""))
        except (KeyError, TypeError):
            level_name = ""
        spatial_base["linked_drainage_area_id"] = int(drain_id)
        spatial_base["linked_drainage_label"] = level_name
        spatial_base["resolution"] = "health_unit_environmental_linkage"
        return (spatial_base, "L2_health_dept_full")

    # Engineering & Planning: spatial context without cross-domain drainage IDs on health events.
    return (spatial_base, "L1_peer_dept_spatial")


def health_events(
    *,
    role: Role,
    disease: str | None,
    year: int | None,
    limit: int,
) -> list[UnifiedEvent]:
    df = _load_health_df()
    if disease:
        df = df[df["Disease"].str.contains(disease, case=False, na=False)]
    if year is not None:
        df = df[df["Year"] == year]
    if df.empty:
        return []
    df = df.copy()
    df["WR Count"] = pd.to_numeric(df["WR Count"], errors="coerce").fillna(0).astype(int)
    df = df.nlargest(min(limit, len(df)), "WR Count", keep="all")
    centroids = planning_community_centroids()
    drain_df = _load_drainage_df()
    drain_lookup = drain_df.set_index("SANDRAINAGEAREAID")

    events: list[UnifiedEvent] = []
    for _, row in df.head(limit).iterrows():
        d = str(row["Disease"])
        y = int(row["Year"])
        g = str(row["Gender"])
        count = int(row["WR Count"])
        rate = row.get("WR Crude Rate per 100000", "")
        pc_id = pick_community_id(d, y, g)
        c = centroids.get(pc_id, {"lon": -80.4936, "lat": 43.4516, "n_applications": 0})
        drain_id = pick_drainage_id(d, y, g)
        spatial, access = _health_spatial_for_role(
            role, pc_id=pc_id, c=c, drain_id=drain_id, drain_lookup=drain_lookup
        )

        events.append(
            UnifiedEvent(
                id=f"med:{_h(d, str(y), g)}",
                event_type="medical",
                source_department="public_health_unit",
                temporal={"year": y},
                spatial=spatial,
                payload={
                    "disease": d,
                    "gender": g,
                    "case_count": count,
                    "wr_crude_rate_per_100k": rate,
                    "note": "Counts from open data; community linkage is deterministic demo keying.",
                },
                access_level=access,
                pii_stripped=True,
            )
        )
    return events


def _engineering_full_payload(aid: int, name: str, wqi: int, maintenance_flag: bool) -> dict:
    return {
        "sandrainageareaid": aid,
        "level_name": name,
        "water_quality_index": wqi,
        "maintenance_recent": maintenance_flag,
    }


def engineering_events(*, role: Role, limit: int) -> list[UnifiedEvent]:
    df = _load_drainage_df().head(limit)
    events: list[UnifiedEvent] = []
    base_lon, base_lat = -80.4936, 43.4516
    full_detail = role in (Role.DEPT_ENGINEERING, Role.DEPT_PUBLIC_HEALTH)

    for _, row in df.iterrows():
        aid = int(row["SANDRAINAGEAREAID"])
        name = str(row.get("LEVEL_NAME", ""))
        dx = (_h(str(aid), "x") % 1000) / 80000 - 0.00625
        dy = (_h(str(aid), "y") % 1000) / 80000 - 0.00625
        lon, lat = base_lon + dx, base_lat + dy
        wqi = 55 + (_h(name, str(aid)) % 35)
        maintenance_flag = (_h(name) % 7) == 0

        if full_detail:
            payload = _engineering_full_payload(aid, name, wqi, maintenance_flag)
            access = "L2_eng_dept_full" if role == Role.DEPT_ENGINEERING else "L1_eng_peer_to_health"
        else:
            payload = {
                "sandrainageareaid": aid,
                "water_quality_index": wqi,
                "status": "summary_only",
            }
            access = "L0_eng_public_or_peer_summary"

        events.append(
            UnifiedEvent(
                id=f"infra:{aid}",
                event_type="infra",
                source_department="city_engineering",
                temporal={
                    "observed": "synthetic_demo_window",
                    "record_time": "gis_extract_snapshot",
                },
                spatial={
                    "location_key": f"drainage:{aid}",
                    "geojson": {"type": "Point", "coordinates": [lon, lat]},
                },
                payload=payload,
                access_level=access,
                pii_stripped=True,
            )
        )
    return events


def planning_events(*, role: Role, limit: int) -> list[UnifiedEvent]:
    df = _load_planning_df().head(limit)
    events: list[UnifiedEvent] = []
    for _, row in df.iterrows():
        try:
            lon, lat = _to_lonlat(row["X"], row["Y"])
        except Exception:
            continue
        app_no = str(row.get("APPLICATION_NO", ""))
        pc_id = int(row["PLANNINGCOMMUNITYID"])
        addr = str(row.get("ADDRESS", ""))
        land = str(row.get("PROPOSED_LANDUSE", row.get("EXISTING_LANDUSE", "")))
        applicant = str(row.get("APPLICANT", ""))
        status = str(row.get("STATUS", ""))

        if role == Role.PUBLIC:
            addr_out = "REDACTED (public preview)"
            applicant_out = "REDACTED"
            contacts: dict = {}
            pii = True
            access = "L0_planning_public"
        elif role == Role.DEPT_PLANNING:
            addr_out = addr
            applicant_out = applicant
            contacts = {
                "contact_email": str(row.get("CONTACT_EMAIL", "")),
                "contact_phone": str(row.get("CONTACT_PHONE", "")),
            }
            pii = False
            access = "L2_planning_dept_full"
        elif role == Role.DEPT_PUBLIC_HEALTH:
            addr_out = addr
            applicant_out = "REDACTED (inter-department policy)"
            contacts = {}
            pii = True
            access = "L1_planning_peer_health"
        else:
            # Engineering peer
            addr_out = addr
            applicant_out = "REDACTED (inter-department policy)"
            contacts = {}
            pii = True
            access = "L1_planning_peer_eng"

        payload = {
            "application_no": app_no,
            "planning_community_id": pc_id,
            "address": addr_out,
            "land_use": land,
            "status": status,
            "applicant": applicant_out,
            **contacts,
        }

        events.append(
            UnifiedEvent(
                id=f"zone:{_h(app_no)}",
                event_type="zone",
                source_department="city_planning",
                temporal={
                    "indate": str(row.get("INDATE", "")),
                    "record_time": "amanda_export_snapshot",
                },
                spatial={
                    "location_key": f"planning_community:{pc_id}",
                    "geojson": {"type": "Point", "coordinates": [lon, lat]},
                },
                payload=payload,
                access_level=access,
                pii_stripped=pii,
            )
        )
    return events


def scenario_bundle(
    *,
    role: Role,
    disease: str | None,
    year: int | None,
    per_source_limit: int,
) -> dict:
    health = health_events(role=role, disease=disease, year=year, limit=per_source_limit)
    infra = engineering_events(role=role, limit=per_source_limit)
    zones = planning_events(role=role, limit=per_source_limit)

    insight = {
        "narrative": (
            "Three department JWTs drive different slices of the same federated response. "
            "Public Health sees drainage linkage on medical events; Engineering sees full infra internals; "
            "Planning sees applicant contacts on its own applications. Peers receive minimized PII."
        ),
        "roles": {
            "public": "Health: regional metrics only (no map). Infra & planning: reduced fields.",
            "dept_public_health": "Full health spatial linkage + drainage IDs; peer planning without applicant identity; full infra detail.",
            "dept_engineering": "Full infra; health community centroids; planning address without applicant/contact.",
            "dept_planning": "Full planning records including contacts; health centroids; infra summaries only.",
        },
    }
    return {
        "schema_profile": "demo_municipal_interchange_v2_departments",
        "lineage": {
            "sources": [
                str(HEALTH_CSV.name),
                str(DRAINAGE_CSV.name),
                str(PLANNING_CSV.name),
            ],
            "join_logic": "Deterministic spatial keys + RBAC field filtering (not a merged warehouse).",
        },
        "insight": insight,
        "layers": {
            "medical": [e.model_dump() for e in health],
            "infra": [e.model_dump() for e in infra],
            "zone": [e.model_dump() for e in zones],
        },
    }


def replace_dataset_file(*, target: Path, content: bytes) -> Path:
    """Write CSV to data dir with backup. Caller must validate first."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if target.is_file():
        backup = BACKUP_DIR / f"{ts}_{target.name}"
        shutil.copy2(target, backup)
    target.write_bytes(content)
    clear_data_caches()
    return target
