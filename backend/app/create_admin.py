from getpass import getpass

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


def main() -> None:
    email = input("Admin email: ").strip().casefold()
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    with SessionLocal.begin() as session:
        if session.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("An account with this email already exists")
        session.add(User(email=email, password_hash=hash_password(password), role="admin", is_active=True))
    print(f"Administrator account created for {email}")


if __name__ == "__main__":
    main()
