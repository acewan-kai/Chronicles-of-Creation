"""
Pre-Sprint: 用户认证系统
JWT登录/注册，密码哈希，Token验证
"""
import os
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Header
import jwt

# JWT配置
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production-!!")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "72"))


def hash_password(password: str) -> str:
    """使用 PBKDF2-SHA256 哈希密码（无需 bcrypt 依赖）"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt, pwd_hash = hashed.split("$", 1)
        verify = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000)
        return verify.hex() == pwd_hash
    except (ValueError, AttributeError):
        return False


def create_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> Optional[str]:
    """从请求头中提取当前用户ID（可选认证）"""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    payload = decode_token(token)
    return payload.get("sub") if payload else None


async def require_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> str:
    """要求用户必须已认证（强依赖）"""
    user_id = await get_current_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="需要登录认证")
    return user_id
