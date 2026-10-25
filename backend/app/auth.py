from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.settings import ACCESS_TOKEN_MINUTES, IS_PRODUCTION, SECRET_KEY


password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except Exception:
        return False


# Verified against when the email is unknown, so a missing account costs the
# same Argon2 work as a wrong password and response time does not reveal
# which emails exist.
_DUMMY_HASH = password_hash.hash("raktsanket-timing-equalizer")


def verify_login(user: User | None, password: str) -> bool:
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, user.password_hash)


class LoginThrottle:
    """Failed-login limiter: per account (stops password guessing on one
    email) and per client address (stops spraying across many emails).

    State is in process memory, which covers a single API process. Behind
    several workers or replicas each process counts separately, so put a
    shared limiter (reverse proxy / API gateway / Redis) in front as well."""

    def __init__(self, max_per_account: int = 5, max_per_client: int = 30, window_seconds: int = 900) -> None:
        self.max_per_account = max_per_account
        self.max_per_client = max_per_client
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        entries = self._failures[key]
        while entries and now - entries[0] > self.window:
            entries.popleft()
        return entries

    def retry_after(self, email: str, client: str) -> int:
        """Seconds until another attempt is allowed, 0 when allowed now."""
        now = monotonic()
        with self._lock:
            waits = []
            for key, limit in ((f"account:{email}", self.max_per_account), (f"client:{client}", self.max_per_client)):
                entries = self._recent(key, now)
                if len(entries) >= limit:
                    waits.append(int(self.window - (now - entries[0])) + 1)
            return max(waits, default=0)

    def record_failure(self, email: str, client: str) -> None:
        now = monotonic()
        with self._lock:
            self._recent(f"account:{email}", now).append(now)
            self._recent(f"client:{client}", now).append(now)

    def record_success(self, email: str) -> None:
        with self._lock:
            self._failures.pop(f"account:{email}", None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_throttle = LoginThrottle()


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": "raktsanket-api",
        "aud": "raktsanket-client",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        if not IS_PRODUCTION:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})

    try:
        claims = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer="raktsanket-api",
            audience="raktsanket-client",
        )
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}) from error

    user = session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None or user.role != claims.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user: User | None = Depends(get_current_user)) -> User | None:
    if user is None and not IS_PRODUCTION:
        return None
    if user is None or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def authorize_donor_access(donor_id: int, user: User | None) -> None:
    if user is None and not IS_PRODUCTION:
        return
    if user is None or user.role != "donor" or user.donor_id != donor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this donor record is not allowed")