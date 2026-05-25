from __future__ import annotations
from typing import Optional
import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    settings = get_settings()
    try:
        if settings.firebase_credentials_path:
            credential_path = Path(settings.firebase_credentials_path)
            if credential_path.exists():
                cred = credentials.Certificate(str(credential_path))
                firebase_admin.initialize_app(cred)
                return
            else:
                logger.warning(f"Firebase credentials not found at: {credential_path}")
        
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            firebase_admin.initialize_app()
    except Exception as exc:
        logger.error(f"Failed to initialize Firebase: {exc}")


def get_firestore_client() -> Optional[Client]:
    if not firebase_admin._apps:
        initialize_firebase()
    if not firebase_admin._apps:
        return None
    try:
        return firestore.client()
    except Exception:
        return None
