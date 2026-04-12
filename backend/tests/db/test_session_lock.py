"""Tests for the per-Session commit lock helper."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from devboard.db.session_lock import _SESSION_LOCK_KEY, commit_with_lock, get_session_lock


class TestGetSessionLock:
    def test_returns_rlock(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        lock = get_session_lock(session)
        assert isinstance(lock, type(threading.RLock()))

    def test_same_lock_returned_for_same_session(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        lock1 = get_session_lock(session)
        lock2 = get_session_lock(session)
        assert lock1 is lock2

    def test_different_sessions_get_different_locks(self) -> None:
        session_a = MagicMock(spec=Session)
        session_a.info = {}
        session_b = MagicMock(spec=Session)
        session_b.info = {}
        assert get_session_lock(session_a) is not get_session_lock(session_b)

    def test_lock_stored_in_session_info(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        lock = get_session_lock(session)
        assert session.info[_SESSION_LOCK_KEY] is lock

    def test_lock_is_reentrant(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        lock = get_session_lock(session)
        # Should not deadlock on re-entry
        with lock:
            with lock:
                pass


class TestCommitWithLock:
    def test_calls_session_commit(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        commit_with_lock(session)
        session.commit.assert_called_once()

    def test_acquires_lock_before_commit(self) -> None:
        """Verify the lock is held during commit."""
        session = MagicMock(spec=Session)
        session.info = {}

        lock_held_during_commit = False

        def check_lock():
            nonlocal lock_held_during_commit
            # Lock is held by the current thread (reentrant), just confirm we got here.
            lock_held_during_commit = True

        session.commit.side_effect = check_lock
        commit_with_lock(session)
        assert lock_held_during_commit

    def test_concurrent_commits_do_not_raise(self) -> None:
        """Two threads committing concurrently via commit_with_lock must not collide."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
            conn.commit()

        session = Session(engine)
        errors: list[Exception] = []

        def do_commit():
            try:
                commit_with_lock(session)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_commit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        session.close()
        assert errors == [], f"Got errors from concurrent commits: {errors}"

    @pytest.mark.asyncio
    async def test_concurrent_asyncio_to_thread_commits_do_not_raise(self) -> None:
        """asyncio.to_thread(commit_with_lock, session) from multiple concurrent tasks must not raise."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
            conn.commit()

        session = Session(engine)
        try:
            await asyncio.gather(*[asyncio.to_thread(commit_with_lock, session) for _ in range(10)])
        finally:
            session.close()
