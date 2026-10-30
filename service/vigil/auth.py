from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from vigil.config import settings
from vigil.db import postgres

# tokenUrl points at the real login endpoint -- this is what makes
# FastAPI's interactive /docs page show a working "Authorize" button
# rather than a decorative one.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain.encode(), password_hash.encode())


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class CurrentUser:
    def __init__(self, username: str, role: str):
        self.username = username
        self.role = role


def get_current_user(token: str = Depends(_oauth2_scheme)) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise credentials_error
    username = payload.get("sub")
    role = payload.get("role")
    if username is None or role is None:
        raise credentials_error
    return CurrentUser(username=username, role=role)


# Two demo accounts, seeded idempotently on every startup (see
# main.py's lifespan). This is a deliberate, documented stand-in for a
# real user-provisioning flow (which this project has no reason to
# build -- there's no real HR/identity system behind it) -- not a
# hidden default a real deployment would accidentally inherit. The
# credentials are named plainly in README.md, not hidden, because
# pretending a demo system has real secrets would be dishonest in the
# other direction.
_DEMO_USERS = [
    ("analyst1", "analyst1-pass", "analyst"),
    ("reviewer1", "reviewer1-pass", "reviewer"),
]


def seed_demo_users() -> None:
    for username, plain_password, role in _DEMO_USERS:
        postgres.create_user(username, hash_password(plain_password), role)
