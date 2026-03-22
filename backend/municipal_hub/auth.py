from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from municipal_hub.schema import Role

SECRET_KEY = os.environ.get("MUNI_HUB_JWT_SECRET", "hackathon-demo-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

security = HTTPBearer(auto_error=False)


def create_access_token(*, sub: str, role: Role) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


async def get_current_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    if creds is None or not creds.credentials:
        return {"sub": "anonymous", "role": Role.PUBLIC.value}
    try:
        return decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def role_from_principal(p: dict) -> Role:
    raw = p.get("role", Role.PUBLIC.value)
    legacy = {
        "planner": Role.DEPT_PLANNING,
        "health_official": Role.DEPT_PUBLIC_HEALTH,
    }
    if raw in legacy:
        return legacy[raw]
    try:
        return Role(raw)
    except ValueError:
        return Role.PUBLIC


def parse_token_role_string(raw: str | Role) -> Role:
    """Accept current department roles plus legacy `planner` / `health_official` aliases."""
    if isinstance(raw, Role):
        return raw
    s = (raw or "").strip()
    if not s:
        return Role.PUBLIC
    legacy = {
        "planner": Role.DEPT_PLANNING,
        "health_official": Role.DEPT_PUBLIC_HEALTH,
    }
    if s in legacy:
        return legacy[s]
    try:
        return Role(s)
    except ValueError:
        allowed = [r.value for r in Role] + list(legacy.keys())
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_role",
                "message": f"Unknown role: {s!r}",
                "allowed": allowed,
            },
        )
