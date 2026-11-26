import os
from typing import Optional

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt


def _secret() -> str:
    # đọc lúc gọi (không phải lúc import) để chắc chắn .env đã được load
    return os.getenv("JWT_SECRET", "dev-secret-change-me")


def decode_token(authorization: Optional[str]) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        data = jwt.decode(authorization[7:].strip(), _secret(), algorithms=["HS256"])
    except JWTError:
        return None
    return {"id": data["sub"], "email": data.get("email", ""), "ev": bool(data.get("ev", False))}


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    user = decode_token(authorization)
    if not user:
        raise HTTPException(401, "Can dang nhap")
    return user


def verified_user(user: dict = Depends(current_user)) -> dict:
    if not user["ev"]:
        raise HTTPException(403, "Hay xac minh email truoc khi dung chuc nang nay")
    return user