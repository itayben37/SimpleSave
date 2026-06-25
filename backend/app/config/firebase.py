import firebase_admin
from firebase_admin import credentials, auth, storage

from app.config.settings import settings

_app: firebase_admin.App | None = None


def init_firebase() -> None:
    global _app
    if _app is not None:
        return
    cred = credentials.Certificate(settings.firebase_credentials_path)
    _app = firebase_admin.initialize_app(
        cred,
        {"storageBucket": settings.firebase_storage_bucket},
    )


def get_firebase_auth() -> auth.Client:
    return auth.Client(firebase_admin.get_app())
