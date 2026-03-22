"""Pre-ingest validation before CSV replaces departmental extracts (demo)."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
YEAR_MIN, YEAR_MAX = 1990, 2035


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_health_csv(content: bytes) -> dict:
    """
    QA rules (hackathon narrative):
    - Required columns; Year in range; WR Count non-negative integer.
    - Crude rate per 100k must not exceed 100,000 (impossible — reject).
    - Warnings: sparse years, N/A rates coerced.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if len(content) > MAX_UPLOAD_BYTES:
        errors.append("File exceeds maximum size (5 MB).")
        return _result(False, errors, warnings, {})

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        errors.append(f"CSV parse error: {e}")
        return _result(False, errors, warnings, {})

    df.columns = [str(c).strip() for c in df.columns]
    required = ["Year", "Disease", "Gender", "WR Count"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    if errors:
        return _result(False, errors, warnings, {})

    years = pd.to_numeric(df["Year"], errors="coerce")
    if years.isna().any():
        errors.append("Year must be numeric for all rows.")
    elif ((years < YEAR_MIN) | (years > YEAR_MAX)).any():
        bad = int(((years < YEAR_MIN) | (years > YEAR_MAX)).sum())
        errors.append(f"{bad} row(s): Year outside allowed range [{YEAR_MIN}, {YEAR_MAX}].")

    counts = pd.to_numeric(df["WR Count"], errors="coerce")
    if counts.isna().any():
        errors.append("WR Count must be numeric for all rows.")
    elif (counts < 0).any():
        errors.append("WR Count must be non-negative.")

    rate_col = "WR Crude Rate per 100000"
    if rate_col in df.columns:
        rates = pd.to_numeric(df[rate_col], errors="coerce")
        na_rates = rates.isna().sum()
        if na_rates:
            warnings.append(f"{int(na_rates)} row(s): crude rate missing or non-numeric (coerced for checks).")
        valid = rates.dropna()
        if len(valid) and (valid > 100_000).any():
            n = int((valid > 100_000).sum())
            errors.append(
                f"Data quality gate: {n} row(s) have WR crude rate > 100,000 per 100k — "
                "physically impossible; upload rejected (demo QA policy)."
            )
        if len(valid) and (valid < 0).any():
            errors.append("Negative crude rates are not allowed.")

    if len(df) < 10:
        warnings.append("Very few rows — dataset may be incomplete (flagged provisional if accepted).")

    quality_meta = {
        "record_time": _now_iso(),
        "observation_time": "column:Year (annual surveillance granularity)",
        "row_count": len(df),
        "temporal_consistency_note": "Health is annual; engineering/planning may be finer — align in analysis.",
    }

    if errors:
        return _result(False, errors, warnings, quality_meta)

    score = 1.0
    score -= 0.07 * len(warnings)
    score = max(0.5, round(score, 2))
    status = "approved" if not warnings else "provisional"
    quality_meta["quality_score"] = score
    quality_meta["status"] = status
    return _result(True, errors, warnings, quality_meta)


def validate_drainage_csv(content: bytes) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if len(content) > MAX_UPLOAD_BYTES:
        errors.append("File exceeds maximum size (5 MB).")
        return _result(False, errors, warnings, {})

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        errors.append(f"CSV parse error: {e}")
        return _result(False, errors, warnings, {})

    if "SANDRAINAGEAREAID" not in df.columns:
        errors.append("Missing required column: SANDRAINAGEAREAID")
        return _result(False, errors, warnings, {})

    ids = pd.to_numeric(df["SANDRAINAGEAREAID"], errors="coerce")
    if ids.isna().any():
        errors.append("SANDRAINAGEAREAID must be numeric for all rows.")

    if errors:
        return _result(False, errors, warnings, {})

    dup = df["SANDRAINAGEAREAID"].duplicated().sum()
    if dup:
        warnings.append(f"{int(dup)} duplicate SANDRAINAGEAREAID values (allowed for demo but unusual).")

    quality_meta = {
        "record_time": _now_iso(),
        "observation_time": "legacy GIS extract (as-of upload)",
        "row_count": len(df),
        "quality_score": 1.0 if not warnings else 0.88,
        "status": "approved" if not warnings else "provisional",
    }
    return _result(True, errors, warnings, quality_meta)


def validate_planning_csv(content: bytes) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if len(content) > MAX_UPLOAD_BYTES:
        errors.append("File exceeds maximum size (5 MB).")
        return _result(False, errors, warnings, {})

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        errors.append(f"CSV parse error: {e}")
        return _result(False, errors, warnings, {})

    for col in ("X", "Y", "PLANNINGCOMMUNITYID", "APPLICATION_NO"):
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if errors:
        return _result(False, errors, warnings, {})

    for col in ("X", "Y"):
        v = pd.to_numeric(df[col], errors="coerce")
        if v.isna().any():
            errors.append(f"Column {col} must be numeric for all rows.")

    pc = pd.to_numeric(df["PLANNINGCOMMUNITYID"], errors="coerce")
    if pc.isna().any():
        errors.append("PLANNINGCOMMUNITYID must be numeric for all rows.")

    if errors:
        return _result(False, errors, warnings, {})

    # Kitchener NAD83 UTM 17N rough bbox (demo sanity)
    x, y = df["X"].astype(float), df["Y"].astype(float)
    if (x < 400000).any() or (x > 800000).any() or (y < 4700000).any() or (y > 4850000).any():
        warnings.append("Some coordinates fall outside expected Kitchener UTM 17N envelope — verify CRS.")

    quality_meta = {
        "record_time": _now_iso(),
        "observation_time": "column:INDATE where present; else upload time",
        "row_count": len(df),
        "quality_score": 1.0 if not warnings else 0.85,
        "status": "approved" if not warnings else "provisional",
    }
    return _result(True, errors, warnings, quality_meta)


def _result(ok: bool, errors: list[str], warnings: list[str], quality: dict) -> dict:
    return {"ok": ok, "errors": errors, "warnings": warnings, "quality": quality}
