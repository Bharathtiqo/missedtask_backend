"""
Utility to copy data from the local MySQL database into the Render PostgreSQL database.
Run from the project root:  python mysql_to_postgres.py
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

# --------------------------------------------------------------------------- #
# Make sure our repo root and the `api` package are on sys.path
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.models import (  # noqa: E402 - imported after sys.path fix
    Base,
    Channel,
    ChannelMembership,
    Conversation,
    ConversationMessage,
    Issue,
    Organization,
    User,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()

# You can override these via environment variables if needed
MYSQL_URL = os.getenv(
    "MYSQL_SOURCE_URL",
    "mysql+pymysql://root:Bharath%401234@localhost:3306/missedtask",
)
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env before running.")

# Order matters: respect foreign-key dependencies
TABLE_ORDER = [
    Organization,
    User,
    Issue,
    Channel,
    ChannelMembership,
    Conversation,
    ConversationMessage,
]

CHUNK_SIZE = 500  # adjust if you want larger/smaller batches


# --------------------------------------------------------------------------- #
# Session helpers
# --------------------------------------------------------------------------- #
def build_session(url: str) -> sessionmaker:
    engine = create_engine(url)
    return sessionmaker(bind=engine)


MySQLSession = build_session(MYSQL_URL)
PostgresSession = build_session(POSTGRES_URL)


@contextmanager
def session_scope(session_factory: sessionmaker) -> Iterable[Session]:
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Migration logic
# --------------------------------------------------------------------------- #
def count_rows(session_factory: sessionmaker, model) -> int:
    with session_scope(session_factory) as session:
        return session.query(model).count()


def copy_table(model) -> None:
    table_name = model.__tablename__
    total = count_rows(MySQLSession, model)

    if total == 0:
        print(f"Skipping {table_name}: no rows to transfer.")
        return

    print(f"Transferring {table_name} ({total} rows)...", end=" ")

    transferred = 0
    try:
        with session_scope(MySQLSession) as src_session:
            query = src_session.query(model).yield_per(CHUNK_SIZE)

            with session_scope(PostgresSession) as dst_session:
                for row in query:
                    dst_session.merge(row)
                    transferred += 1
                    if transferred % CHUNK_SIZE == 0:
                        dst_session.flush()

    except SQLAlchemyError as exc:  # catch DB-specific errors
        print("FAILED")
        raise RuntimeError(f"Failed while copying {table_name}") from exc

    print(f"done ({transferred} rows).")


def main() -> None:
    print("=" * 60)
    print(" MySQL → PostgreSQL data transfer")
    print("=" * 60)
    print(f"MySQL source : {MYSQL_URL}")
    print(f"Postgres dest: {POSTGRES_URL}")
    print()

    # Make sure the destination schema exists
    print("Ensuring destination tables exist...")
    Base.metadata.create_all(bind=create_engine(POSTGRES_URL))
    print("Tables ready.\n")

    for model in TABLE_ORDER:
        copy_table(model)

    print("\nAll transfers complete.")


if __name__ == "__main__":
    main()
