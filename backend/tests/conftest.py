import pytest
from pytest import fixture
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from devboard.db.models import Base
from devboard.db.session import DBSessionMaker


@fixture(scope="session")
def db_engine() -> Engine:
    """
    Fixture which returns a SQLAlchemy engine for in-memory SQLite database for testing.
    """
    yield create_engine("sqlite:///:memory:", echo=True)


@fixture(scope="session")
def db_connection(db_engine: Engine) -> Connection:
    """
    Fixture to provide a SQLAlchemy connection for the containerised database.
    This connection is re-used for the entire test session.
    """
    with db_engine.connect() as connection:
        yield connection


@fixture(scope="session")
def db_tables(db_connection):
    """
    Fixture to create all the tables in the database.
    Dropping tables afterwards should not be necessary since the entire container will be cleared
    """
    with db_connection.begin():
        Base.metadata.create_all(db_connection)
    yield


@fixture()
def db_session_maker(db_connection: Connection, db_tables) -> DBSessionMaker:
    """
    Provides a SQLAlchemy DB session for each test
    (within a transaction, so changes will be rolled back after each test).
    Also patches the Dippy-registered DBSession with this test session.
    """
    # If using requests_mock, can disable it for localhost container requests like:
    # requests_mock.register_uri(requests_mock_lib.ANY, re.compile("localhost/"), real_http=True)
    with db_connection.begin() as transaction:
        # Set join_transaction_mode so that subsequent nested transactions are implemented as savepoints,
        # so that this outer transaction does not become broken during a rollback.
        session_maker = DBSessionMaker(bind=db_connection, join_transaction_mode="create_savepoint")
        yield session_maker
        # Rollback transaction so that each test is isolated
        transaction.rollback()


@fixture()
def db_session(db_session_maker: DBSessionMaker) -> Session:
    """
    Provides a SQLAlchemy DB session with an open transaction
    """
    with db_session_maker.begin() as session:
        yield session
