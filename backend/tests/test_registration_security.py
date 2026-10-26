from datetime import datetime,timezone,timedelta
import pytest,httpx
from fastapi import HTTPException
from test_auth import client,register
from human_verification import require_human,verify_token,public_settings
import human_verification
from password_policy import password_problem
from models import User
from sqlalchemy import select,func

@pytest.mark.parametrize('value',['Password123456789!','passwordpassword123','qwertyuiopasdfghjkl','correct horse battery staple','11111111111111111111','TestUser123456789!'])
def test_rejects_predictable_passwords_without_echo(client,value):
    result=register(client,password=value)
    assert result.status_code==422
    assert value not in result.text
    assert all('input' not in entry for entry in result.json()['detail'])
    with client.sessions() as db:assert db.scalar(select(func.count()).select_from(User))==0

def test_accepts_long_original_passphrases_and_full_length():
    assert password_problem('cobalt lanterns drift beyond seven orchards') is None
    assert password_problem('cobalt lanterns drift beyond seven orchards '+('lilac river '+ 'violet breeze ')*3) is None
    assert password_problem('x'*129)

def configure(monkeypatch):
    monkeypatch.setenv('TURNSTILE_SITE_KEY','fixture-public-widget-key')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY','fixture-private-verification-key')
    monkeypatch.setenv('TURNSTILE_MODE','required')
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES','localhost,127.0.0.1')

def mock_service(monkeypatch,body,status=200):
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,data):
            assert 'password' not in data
            assert set(data)=={'secret','response'}
            return httpx.Response(status,json=body,request=httpx.Request('POST',url))
    monkeypatch.setattr(human_verification.httpx,'Client',Client)

def result(**changes):
    return {'success':True,'hostname':'localhost','action':'register','challenge_ts':datetime.now(timezone.utc).isoformat(),**changes}

def test_configuration_never_exposes_secret(client,monkeypatch):
    configure(monkeypatch)
    value=client.get('/auth/config')
    assert value.status_code==200 and value.json()['human_verification']['ready'] is True
    assert 'fixture-private-verification-key' not in value.text

def test_missing_settings_fail_closed_and_login_works(client,monkeypatch):
    monkeypatch.delenv('TURNSTILE_SECRET_KEY',raising=False)
    app=__import__('main').app
    app.dependency_overrides.pop(require_human)
    response=register(client)
    assert response.status_code==503
    assert client.get('/auth/config').json()['human_verification']['ready'] is False
    assert client.get('/health').status_code==200

def test_human_success_required_for_real_registration(client,monkeypatch):
    configure(monkeypatch);mock_service(monkeypatch,result())
    __import__('main').app.dependency_overrides.pop(require_human)
    assert register(client).status_code==422
    response=register(client,human_token='fixture-human-token')
    assert response.status_code==201
    assert 'fixture-human-token' not in response.text

@pytest.mark.parametrize('changes',[{'success':False},{'hostname':'attacker.example'},{'hostname':None},{'action':'other'},{'challenge_ts':'invalid'},{'challenge_ts':(datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()}])
def test_bad_failed_or_expired_tokens_are_rejected(monkeypatch,changes):
    configure(monkeypatch);mock_service(monkeypatch,result(**changes))
    with pytest.raises(HTTPException) as error:verify_token('fixture-human-token')
    assert error.value.status_code==422

def test_upstream_failure_never_allows_registration(monkeypatch):
    configure(monkeypatch);mock_service(monkeypatch,{},status=503)
    with pytest.raises(HTTPException) as error:verify_token('fixture-human-token')
    assert error.value.status_code==503

def test_real_mode_rejects_documented_test_keys(monkeypatch):
    configure(monkeypatch);monkeypatch.setenv('TURNSTILE_SECRET_KEY','1x0000000000000000000000000000000AA')
    assert public_settings()['ready'] is False
    with pytest.raises(HTTPException):verify_token('dummy')
