"""Create a staff account (MANAGEMENT or OPERATOR) from the command line.

Why this exists
---------------
`POST /api/v1/auth/register` always creates a COMMUTER, and
`POST /api/v1/auth/users` (the only endpoint that can create a staff
account) requires a MANAGEMENT access token. That is a chicken-and-egg
problem: the very first MANAGEMENT user has to be created directly in the
database. This script does exactly that, and nothing else.

Usage
-----
From the `backend` directory::

    python scripts/create_staff.py --email admin@example.com --password "S3cret!" --role MANAGEMENT

To target a different database (for example the Supabase project) pass the
connection string explicitly, or set `DATABASE_URL` in the environment::

    python scripts/create_staff.py --database-url "postgresql://postgres.REF:PASS@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require" --email admin@example.com --password "S3cret!"

The password is hashed with the same Argon2id implementation the API uses,
so the account can log in through `POST /api/v1/auth/login` immediately.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow `python scripts/create_staff.py` from the backend directory: the
# `app` package lives one level up, so it has to be on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a MANAGEMENT or OPERATOR account directly in the database."
    )
    parser.add_argument("--email", required=True, help="Login email address")
    parser.add_argument("--password", required=True, help="Plaintext password")
    parser.add_argument(
        "--full-name", default="Administrator", help="Display name (default: Administrator)"
    )
    parser.add_argument(
        "--role",
        choices=["MANAGEMENT", "OPERATOR"],
        default="MANAGEMENT",
        help="Role to assign (default: MANAGEMENT)",
    )
    parser.add_argument(
        "--database-url",
        help="Connection string to use instead of the DATABASE_URL from the environment",
    )
    args = parser.parse_args()

    # The connection string has to be in the environment before
    # `app.core.config` is imported, because `Settings` is instantiated at
    # import time and reads the environment once.
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy.exc import IntegrityError

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    role = UserRole(args.role)
    email = args.email.strip().lower()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing is not None:
            print(f"User {email} already exists (role={existing.role.value}).")
            print("Nothing was changed.")
            return 1

        user = User(
            full_name=args.full_name,
            email=email,
            phone=None,
            password_hash=hash_password(args.password),
            role=role,
            is_active=True,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(f"Could not create {email}: the email address is already registered.")
            return 1
        db.refresh(user)

        print(f"Created {role.value} account: {user.email} (id={user.id})")
        print("You can now log in through POST /api/v1/auth/login")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
