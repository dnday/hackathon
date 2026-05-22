from __future__ import annotations
import asyncio

import firebase_admin
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth

from app.core.exceptions import AppError


bearer_scheme = HTTPBearer(auto_error=False)


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    if credentials is None:
        return None
    if not firebase_admin._apps:
        raise AppError("AUTH_UNAVAILABLE", "Firebase authentication is not configured.")

    try:
        return await asyncio.to_thread(auth.verify_id_token, credentials.credentials)
    except Exception as exc:
        raise AppError("INVALID_TOKEN", "Invalid Firebase authentication token.", 401) from exc
