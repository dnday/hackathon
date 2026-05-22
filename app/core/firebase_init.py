from __future__ import annotations
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client

from app.core.config import get_settings


def initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    settings = get_settings()
    if settings.firebase_credentials_path:
        credential_path = Path(settings.firebase_credentials_path)
        cred = credentials.Certificate(str(credential_path))
        firebase_admin.initialize_app(cred)
        return

    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        firebase_admin.initialize_app()


def get_firestore_client() -> Client | None:
    if not firebase_admin._apps:
        initialize_firebase()
    if not firebase_admin._apps:
        return None
    try:
        return firestore.client()
    except Exception:
        return None
