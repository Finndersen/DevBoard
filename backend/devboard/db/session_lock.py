"""Per-Session commit serialization to prevent concurrent flush races."""

import threading

from sqlalchemy.orm import Session

_SESSION_LOCK_KEY = "_devboard_commit_lock"


def get_session_lock(session: Session) -> threading.RLock:
    """Return the per-Session commit lock, lazily creating it.

    Ensures all commits on a shared Session are serialized so worker threads
    (anyio executors running sync tool functions) don't collide with drain-loop commits.
    """
    lock = session.info.get(_SESSION_LOCK_KEY)
    if lock is None:
        lock = threading.RLock()
        session.info[_SESSION_LOCK_KEY] = lock
    return lock


def commit_with_lock(session: Session) -> None:
    """Acquire the Session's commit lock and commit. Safe to call from worker threads."""
    with get_session_lock(session):
        session.commit()
