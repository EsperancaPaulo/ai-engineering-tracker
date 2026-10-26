import os
from datetime import datetime,timezone
import httpx
from fastapi import HTTPException
from schemas import Registration

URL='https://challenges.cloudflare.com/turnstile/v0/siteverify'
TEST_KEYS={'1x00000000000000000000AA','2x00000000000000000000AB','1x00000000000000000000BB','2x00000000000000000000BB','3x00000000000000000000FF',
           '1x0000000000000000000000000000000AA','2x0000000000000000000000000000000AA','3x0000000000000000000000000000000AA'}


def settings():
    mode=os.getenv('TURNSTILE_MODE','required')
    site=os.getenv('TURNSTILE_SITE_KEY','')
    secret=os.getenv('TURNSTILE_SECRET_KEY','')
    hosts={value.strip().lower() for value in os.getenv('TURNSTILE_ALLOWED_HOSTNAMES','localhost,127.0.0.1').split(',') if value.strip()}
    ready=bool(mode in ('required','test') and site and secret and hosts)
    if mode=='required' and (site in TEST_KEYS or secret in TEST_KEYS):ready=False
    return mode,site,secret,hosts,ready


def public_settings():
    mode,site,_,_,ready=settings()
    return {'mode':mode,'ready':ready,'site_key':site if ready else None}


def verify_token(token):
    mode,_,secret,hosts,ready=settings()
    if not ready:raise HTTPException(503,'Registration is waiting for human-verification setup. Existing accounts can still sign in.')
    if not token:raise HTTPException(422,'Complete the human-verification check before creating an account.')
    try:
        with httpx.Client(timeout=httpx.Timeout(8,connect=4),follow_redirects=False,trust_env=False) as client:
            response=client.post(URL,data={'secret':secret,'response':token})
        response.raise_for_status()
        result=response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(503,'Human verification is temporarily unavailable. Please try again.') from None
    if not isinstance(result,dict) or result.get('success') is not True:
        raise HTTPException(422,'Human verification failed or expired. Please complete it again.')
    if mode=='required':
        try:
            timestamp=datetime.fromisoformat(result['challenge_ts'].replace('Z','+00:00'))
            age=(datetime.now(timezone.utc)-timestamp).total_seconds()
        except (KeyError,ValueError,TypeError,AttributeError):
            raise HTTPException(422,'Human verification response could not be validated.') from None
        if not isinstance(result.get('hostname'),str) or result['hostname'].lower() not in hosts or result.get('action')!='register' or not 0<=age<=300:
            raise HTTPException(422,'Human verification does not match this registration. Please try again.')


def require_human(data:Registration):
    verify_token(data.human_token.get_secret_value() if data.human_token else None)
