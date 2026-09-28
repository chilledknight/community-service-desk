"""Shared pytest test fixtures."""

import os

os.environ["CSD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CSD_ENVIRONMENT"] = "testing"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from community_service_desk.config import get_settings

get_settings.cache_clear()
from community_service_desk.database import Base, get_db
from community_service_desk.main import app
from community_service_desk.models.organization import Organization
from community_service_desk.models.queue import Queue
from community_service_desk.models.user import Membership, User
from community_service_desk.services.auth_service import AuthService


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    return test_engine


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionTest = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionTest()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def org_alpha(db) -> Organization:
    org = Organization(name="Alpha Community", slug="alpha-org", status="active")
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def org_beta(db) -> Organization:
    org = Organization(name="Beta Community", slug="beta-org", status="active")
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def user_admin_a(db, org_alpha) -> User:
    u = User(
        email="admin_a@alpha.org",
        display_name="Admin Alpha",
        password_hash=AuthService.hash_password("Password123!"),
        active=True,
    )
    db.add(u)
    db.flush()
    mem = Membership(organization_id=org_alpha.id, user_id=u.id, role="organization_admin")
    db.add(mem)
    db.flush()
    return u


@pytest.fixture
def user_agent_a(db, org_alpha) -> User:
    u = User(
        email="agent_a@alpha.org",
        display_name="Agent Alpha",
        password_hash=AuthService.hash_password("Password123!"),
        active=True,
    )
    db.add(u)
    db.flush()
    mem = Membership(organization_id=org_alpha.id, user_id=u.id, role="agent")
    db.add(mem)
    db.flush()
    return u


@pytest.fixture
def user_requester_a1(db, org_alpha) -> User:
    u = User(
        email="requester1@alpha.org",
        display_name="Requester One",
        password_hash=AuthService.hash_password("Password123!"),
        active=True,
    )
    db.add(u)
    db.flush()
    mem = Membership(organization_id=org_alpha.id, user_id=u.id, role="requester")
    db.add(mem)
    db.flush()
    return u


@pytest.fixture
def user_requester_a2(db, org_alpha) -> User:
    u = User(
        email="requester2@alpha.org",
        display_name="Requester Two",
        password_hash=AuthService.hash_password("Password123!"),
        active=True,
    )
    db.add(u)
    db.flush()
    mem = Membership(organization_id=org_alpha.id, user_id=u.id, role="requester")
    db.add(mem)
    db.flush()
    return u


@pytest.fixture
def user_agent_b(db, org_beta) -> User:
    u = User(
        email="agent_b@beta.org",
        display_name="Agent Beta",
        password_hash=AuthService.hash_password("Password123!"),
        active=True,
    )
    db.add(u)
    db.flush()
    mem = Membership(organization_id=org_beta.id, user_id=u.id, role="agent")
    db.add(mem)
    db.flush()
    return u


@pytest.fixture
def queue_alpha(db, org_alpha) -> Queue:
    q = Queue(organization_id=org_alpha.id, name="IT Support", active=True)
    db.add(q)
    db.flush()
    return q


def make_auth_headers(user: User, org: Organization, role: str) -> dict[str, str]:
    token = AuthService.create_access_token(
        data={"sub": user.id, "email": user.email, "org_id": org.id, "role": role}
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org.id,
    }


@pytest.fixture
def auth_agent_a(user_agent_a, org_alpha) -> dict[str, str]:
    return make_auth_headers(user_agent_a, org_alpha, "agent")


@pytest.fixture
def auth_admin_a(user_admin_a, org_alpha) -> dict[str, str]:
    return make_auth_headers(user_admin_a, org_alpha, "organization_admin")


@pytest.fixture
def auth_req_a1(user_requester_a1, org_alpha) -> dict[str, str]:
    return make_auth_headers(user_requester_a1, org_alpha, "requester")


@pytest.fixture
def auth_req_a2(user_requester_a2, org_alpha) -> dict[str, str]:
    return make_auth_headers(user_requester_a2, org_alpha, "requester")


@pytest.fixture
def auth_agent_b(user_agent_b, org_beta) -> dict[str, str]:
    return make_auth_headers(user_agent_b, org_beta, "agent")
