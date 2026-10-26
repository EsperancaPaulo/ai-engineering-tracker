import os
import secrets
from datetime import datetime, timedelta, timezone

# Never load or connect to the developer's PostgreSQL database during tests.
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['JWT_SECRET_KEY'] = secrets.token_urlsafe(48)
os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'] = '30'

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import auth
from database import Base
from main import app
from models import User

PASSWORD = 'a long unique test passphrase!'


@pytest.fixture()
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def db_override():
        with sessions() as session:
            yield session
    app.dependency_overrides[auth.get_db] = db_override
    with TestClient(app) as client:
        client.sessions = sessions
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, **changes):
    return client.post('/auth/register', json={'name': ' Test User ', 'email': 'Person@Example.com', 'password': PASSWORD, **changes})


def login(client, **changes):
    return client.post('/auth/login', data={'username': 'person@example.com', 'password': PASSWORD, **changes})


def test_full_flow(client):
    result = register(client)
    assert result.status_code == 201
    assert result.json()['name'] == 'Test User'
    assert result.json()['email'] == 'person@example.com'
    assert 'password' not in result.text
    with client.sessions() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith('$argon2id$')
        assert auth.password_hasher.verify(PASSWORD, user.password_hash)
        assert user.role == 'developer'
    result = login(client, username='PERSON@EXAMPLE.COM')
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    assert result.json()['expires_in'] == 1800
    token = result.json()['access_token']
    claims = jwt.decode(token, auth.SECRET_KEY, algorithms=['HS256'], issuer=auth.ISSUER)
    assert claims['exp'] - claims['iat'] == 1800
    result = client.get('/me', headers={'Authorization': f'Bearer {token}'})
    assert result.status_code == 200
    assert result.json()['email'] == 'person@example.com'
    assert 'password' not in result.text


def test_duplicates(client):
    assert register(client).status_code == 201
    assert register(client, email='PERSON@example.com').status_code == 409


@pytest.mark.parametrize('changes', [{'name': ' '}, {'name': 'a' * 101}, {'email': 'bad'}, {'password': 'tiny-secret'}, {'password': 'x' * 129}, {'role': 'admin'}, {'password': None}])
def test_validation_and_no_secret_echo(client, changes):
    result = register(client, **changes)
    assert result.status_code == 422
    assert PASSWORD not in result.text
    assert all('input' not in error for error in result.json()['detail'])
    if changes.get('password'):
        assert changes['password'] not in result.text


def test_bad_credentials(client):
    register(client)
    wrong = login(client, password='incorrect password')
    absent = login(client, username='absent@example.com')
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json() == absent.json()
    assert wrong.headers['www-authenticate'] == 'Bearer'
    assert login(client, password='x' * 129).status_code == 401


@pytest.mark.parametrize('header', [None, 'Basic abc', 'Bearer malformed', 'Bearer '])
def test_no_valid_bearer(client, header):
    result = client.get('/me', headers={'Authorization': header} if header else {})
    assert result.status_code == 401


@pytest.mark.parametrize('kind', ['expired', 'forged', 'missing-exp', 'missing-sub', 'unknown-user', 'bad-sub', 'wrong-issuer', 'wrong-algorithm', 'future', 'large-sub'])
def test_invalid_tokens(client, kind):
    register(client)
    now = datetime.now(timezone.utc)
    claims = {'sub': '1', 'exp': now + timedelta(minutes=5), 'iat': now, 'iss': auth.ISSUER}
    key, algorithm = auth.SECRET_KEY, 'HS256'
    if kind == 'expired': claims['exp'] = now - timedelta(seconds=1)
    if kind == 'forged': key = 'another-secret-key-of-at-least-32-bytes'
    if kind == 'missing-exp': del claims['exp']
    if kind == 'missing-sub': del claims['sub']
    if kind == 'unknown-user': claims['sub'] = '999'
    if kind == 'bad-sub': claims['sub'] = 'admin'
    if kind == 'large-sub': claims['sub'] = '9' * 100
    if kind == 'wrong-issuer': claims['iss'] = 'other'
    if kind == 'wrong-algorithm': algorithm = 'HS384'
    if kind == 'future': claims['iat'] = now + timedelta(minutes=1)
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert client.get('/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_deleted_user(client):
    register(client)
    token = login(client).json()['access_token']
    with client.sessions() as db:
        db.delete(db.get(User, 1))
        db.commit()
    assert client.get('/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_existing_routes(client):
    assert client.get('/').status_code == 200
    assert client.get('/health').json() == {'status': 'healthy'}
