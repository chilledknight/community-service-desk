"""Authentication and password hashing services."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from community_service_desk.config import get_settings
from community_service_desk.models.organization import Organization
from community_service_desk.models.user import Membership, User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    """Handles password hashing, token generation, and user authentication."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Securely hash a password using scrypt with a cryptographic salt."""
        salt = secrets.token_bytes(16)
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=0,
            dklen=64,
        )
        return f"scrypt$16384$8$1${salt.hex()}${key.hex()}"

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against the stored scrypt hash in constant time."""
        try:
            parts = hashed_password.split("$")
            if len(parts) != 6 or parts[0] != "scrypt":
                return False
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt = bytes.fromhex(parts[4])
            stored_key = bytes.fromhex(parts[5])

            derived_key = hashlib.scrypt(
                plain_password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                maxmem=0,
                dklen=len(stored_key),
            )
            return hmac.compare_digest(derived_key, stored_key)
        except Exception:
            return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        """Create a signed JWT access token."""
        settings = get_settings()
        to_encode = data.copy()
        expire = utc_now() + (
            expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
        )
        to_encode.update({"exp": expire, "iat": utc_now()})
        return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    @staticmethod
    def decode_access_token(token: str) -> dict | None:
        """Decode and validate a JWT access token."""
        settings = get_settings()
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except jwt.PyJWTError:
            return None

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        email: str,
        password: str,
        organization_slug: str | None = None,
    ) -> tuple[User, str | None, str | None] | None:
        """Authenticate user credentials and resolve their membership role.

        Returns:
            Tuple of (User, organization_id, role) or None if invalid.
        """
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user or not user.active:
            return None

        if not cls.verify_password(password, user.password_hash):
            return None

        user.last_login_at = utc_now()
        db.commit()

        # Resolve organization membership
        target_org_id = None
        role = None

        if organization_slug:
            org = db.query(Organization).filter(Organization.slug == organization_slug).first()
            if org:
                membership = (
                    db.query(Membership)
                    .filter(
                        Membership.user_id == user.id,
                        Membership.organization_id == org.id,
                    )
                    .first()
                )
                if membership:
                    target_org_id = org.id
                    role = membership.role
        else:
            # Pick first available active membership
            membership = (
                db.query(Membership)
                .join(Organization)
                .filter(
                    Membership.user_id == user.id,
                    Organization.status == "active",
                )
                .first()
            )
            if membership:
                target_org_id = membership.organization_id
                role = membership.role

        return user, target_org_id, role
