from fastapi.testclient import TestClient
from pytest import fixture
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from devboard.api.main import app
from devboard.db.database import get_db
from devboard.db.models import Base


@fixture(scope="session")
def db_engine() -> Engine:
    """
    Fixture which returns a SQLAlchemy engine for in-memory SQLite database for testing.
    """
    yield create_engine(
        "sqlite:///:memory:",
        echo=True,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )


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
def db_session(db_connection: Connection, db_tables) -> Session:
    """
    Provides a SQLAlchemy DB session that automatically rolls back changes after each test.
    """
    # Use savepoint/nested transaction for proper test isolation in SQLite
    nested_trans = db_connection.begin_nested()

    # Create session bound to the connection
    session = Session(bind=db_connection)

    try:
        yield session
    finally:
        # Close session and rollback the savepoint
        session.close()
        nested_trans.rollback()


@fixture
def client(db_session):
    """FastAPI test client with database setup."""

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
