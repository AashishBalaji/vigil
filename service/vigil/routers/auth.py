from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from vigil.auth import create_access_token, verify_password
from vigil.db import postgres
from vigil.schemas import TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = postgres.get_user_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user["password_hash"]):
        # Deliberately identical error for "no such user" and "wrong
        # password" -- a login endpoint that says which one it was
        # tells an attacker whether a username exists at all.
        raise HTTPException(status_code=401, detail="incorrect username or password")
    token = create_access_token(username=user["username"], role=user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}
