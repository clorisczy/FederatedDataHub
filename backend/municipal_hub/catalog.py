from __future__ import annotations

from municipal_hub.schema import CatalogEntry

CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        dataset_id="ph_wr_surveillance_sex",
        department="Public Health (Region of Waterloo)",
        title="Annual infectious disease surveillance by year / disease / sex",
        description="Open aggregate counts; internal addresses never leave the health unit. "
        "Federation exposes planning-community keys only after in-firewall aggregation.",
        endpoint="/internal/adapters/health/raw",
        access_levels=["public", "dept_public_health", "dept_engineering", "dept_planning"],
        common_schema_fields=[
            "event_type",
            "temporal.year",
            "payload.disease",
            "payload.case_count",
            "spatial.location_key",
        ],
        update_cadence="Annual",
    ),
    CatalogEntry(
        dataset_id="eng_sanitary_drainage_areas",
        department="City Engineering — Sanitary drainage",
        title="Sanitary drainage hierarchy (areas / sub-areas)",
        description="Legacy GIS export; adapter maps to infra events with synthetic water-quality index.",
        endpoint="/internal/adapters/engineering/raw",
        access_levels=["public", "dept_public_health", "dept_engineering", "dept_planning"],
        common_schema_fields=[
            "event_type",
            "payload.sandrainageareaid",
            "payload.water_quality_index",
            "spatial.geojson",
        ],
        update_cadence="As engineering updates GIS",
    ),
    CatalogEntry(
        dataset_id="plan_active_applications",
        department="City Planning",
        title="Active / recent planning applications",
        description="AMANDA export; applicant contact details redacted for non-official roles.",
        endpoint="/internal/adapters/planning/raw",
        access_levels=["public", "dept_public_health", "dept_engineering", "dept_planning"],
        common_schema_fields=[
            "event_type",
            "payload.application_no",
            "payload.land_use",
            "spatial.geojson",
            "payload.planning_community_id",
        ],
        update_cadence="Weekly (open data mirror)",
    ),
]
