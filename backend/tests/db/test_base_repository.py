"""Tests for BaseRepository, focusing on the locked commit behavior."""

import threading
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from devboard.db.repositories.base import BaseRepository
from devboard.db.session_lock import _SESSION_LOCK_KEY


class TestBaseRepositoryCommit:
    def test_commit_calls_session_commit(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        repo: BaseRepository[object] = BaseRepository(session)
        repo.commit()
        session.commit.assert_called_once()

    def test_commit_creates_lock_on_session(self) -> None:
        session = MagicMock(spec=Session)
        session.info = {}
        repo: BaseRepository[object] = BaseRepository(session)
        repo.commit()
        assert _SESSION_LOCK_KEY in session.info
        assert isinstance(session.info[_SESSION_LOCK_KEY], type(threading.RLock()))

    def test_concurrent_commits_from_two_threads_do_not_raise(self) -> None:
        """Two repositories sharing a Session can commit concurrently without error."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
            conn.commit()

        session = Session(engine)
        repo: BaseRepository[object] = BaseRepository(session)
        errors: list[Exception] = []

        def do_commit():
            try:
                repo.commit()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_commit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        session.close()
        assert errors == [], f"Got errors from concurrent repo.commit() calls: {errors}"
