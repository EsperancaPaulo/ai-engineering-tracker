"""TLS email links, single-use hashed tokens, and account recovery. Never log secrets."""
import hashlib,os,secrets,smtplib,ssl,threading,time
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,EmailStr,Field,SecretStr
from typing import Literal
from sqlalchemy import select,func
from auth import Database,normalize_email,password_hasher
from tracker import CurrentUser,record
from models import User,UserSecurity,EmailGrant
from password_policy import password_problem

router=APIRouter(prefix='/auth',tags=['Account recovery'])
_requests={};_lock=threading.Lock()


def limit(key,maximum=3,window=3600):
    now=time.monotonic()
    with _lock:
        for old in list(_requests):
            _requests[old]=[stamp for stamp in _requests[old] if now-stamp<3600]
            if not _requests[old]:del _requests[old]
        values=[stamp for stamp in _requests.get(key,[]) if now-stamp<window]
        if len(values)>=maximum or len(_requests)>10000:raise HTTPException(429,'Too many attempts. Please wait before trying again.')
        _requests[key]=[*values,now]


def settings():
    host=os.getenv('SMTP_HOST','').strip()
    try:port=int(os.getenv('SMTP_PORT','587'))
    except ValueError:port=0
    username=os.getenv('SMTP_USERNAME','');password=os.getenv('SMTP_PASSWORD','');sender=os.getenv('SMTP_FROM','')
    base=os.getenv('APP_PUBLIC_URL','http://127.0.0.1:8000').rstrip('/')
    try:parsed=urlsplit(base)
    except ValueError:parsed=urlsplit('invalid:')
    valid=bool(parsed.hostname) and (parsed.scheme=='https' or parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1')) and parsed.path in ('','/')
    ready=bool(host and port in (465,587) and username and password and sender and valid and not parsed.username and not parsed.query and not parsed.fragment)
    return {'host':host,'port':port,'username':username,'password':password,'sender':sender,'base':base,'ready':ready}


def send_mail(config,to,kind,token):
    link=config['base']+('/#reset=' if kind=='reset' else '/#verify=')+token
    mail=EmailMessage();mail['From']=config['sender'];mail['To']=to
    mail['Subject']='Reset your AI Engineering Tracker password' if kind=='reset' else 'Verify your AI Engineering Tracker email'
    mail.set_content(('Reset your password' if kind=='reset' else 'Verify your email')+' using this single-use link within 30 minutes:\n\n'+link+'\n\nIf you did not request this, ignore this message.')
    context=ssl.create_default_context()
    if config['port']==465:
        with smtplib.SMTP_SSL(config['host'],465,timeout=10,context=context) as client:
            client.login(config['username'],config['password']);client.send_message(mail)
    else:
        with smtplib.SMTP(config['host'],587,timeout=10) as client:
            client.ehlo();client.starttls(context=context);client.ehlo();client.login(config['username'],config['password']);client.send_message(mail)


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:EmailStr=Field(max_length=255)
    kind:Literal['reset','verify']='reset'


class GrantInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token:SecretStr=Field(min_length=20,max_length=128)


class ResetInput(GrantInput):
    password:SecretStr=Field(min_length=15,max_length=128)


@router.get('/account')
def account(db:Database,user:CurrentUser):
    state=db.get(UserSecurity,user.id)
    return {'email_verified':bool(state and state.email_verified_at),'email_service_ready':settings()['ready'],'notifications_enabled':state.notifications_enabled if state else True}


@router.post('/email-action')
def request_action(data:ActionRequest,request:Request,db:Database):
    config=settings()
    if not config['ready']:raise HTTPException(503,'Account email is not configured yet. Existing sign-in still works.')
    limit('email-ip:'+str(request.client.host if request.client else 'unknown'),10)
    email=normalize_email(str(data.email));limit('email:'+hashlib.sha256(email.encode()).hexdigest(),3)
    user=db.scalar(select(User).where(func.lower(User.email)==email))
    if user:
        token=secrets.token_urlsafe(32)
        db.add(EmailGrant(token_digest=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,kind=data.kind,expires_at=datetime.now(timezone.utc)+timedelta(minutes=30)))
        recipient=user.email;db.commit()
        try:send_mail(config,recipient,data.kind,token)
        except (smtplib.SMTPException,OSError,ValueError):raise HTTPException(503,'The email service could not confirm delivery. Try later; do not share your account link.') from None
    return {'message':'If this account exists, a single-use email link has been sent.'}


def consume(db,token,kind):
    token_digest=hashlib.sha256(token.encode()).hexdigest()
    initial=db.get(EmailGrant,token_digest)
    if not initial:raise HTTPException(422,'This account link is invalid, expired or already used. Request a new one.')
    # Lock the account before any grant to serialize concurrent links/resets.
    user=db.scalar(select(User).where(User.id==initial.user_id).with_for_update())
    value=db.scalar(select(EmailGrant).where(EmailGrant.token_digest==token_digest).with_for_update().execution_options(populate_existing=True))
    now=datetime.now(timezone.utc)
    expiry=value.expires_at.replace(tzinfo=timezone.utc) if value and value.expires_at.tzinfo is None else value.expires_at.astimezone(timezone.utc) if value else now
    if not value or value.kind!=kind or value.consumed or expiry<now:
        raise HTTPException(422,'This account link is invalid, expired or already used. Request a new one.')
    if not user:raise HTTPException(422,'This account link is unavailable.')
    return value,user


def security_state(db,user):
    state=db.get(UserSecurity,user.id)
    if not state:state=UserSecurity(user_id=user.id,session_version=0);db.add(state);db.flush()
    return state


@router.post('/verify-email')
def verify(data:GrantInput,db:Database):
    value,user=consume(db,data.token.get_secret_value(),'verify')
    state=security_state(db,user);state.email_verified_at=datetime.now(timezone.utc);value.consumed=True
    record(db,user,'Email verified','Account email verified');db.commit()
    return {'message':'Your email is verified. You can sign in.'}


@router.post('/reset-password')
def reset(data:ResetInput,db:Database):
    value,user=consume(db,data.token.get_secret_value(),'reset')
    problem=password_problem(data.password.get_secret_value(),user.name,user.email)
    if problem:raise HTTPException(422,problem)
    state=security_state(db,user)
    user.password_hash=password_hasher.hash(data.password.get_secret_value());state.session_version+=1;state.email_verified_at=datetime.now(timezone.utc)
    value.consumed=True
    # Invalidate every outstanding reset/verification grant for this account.
    for grant in db.scalars(select(EmailGrant).where(EmailGrant.user_id==user.id)):grant.consumed=True
    record(db,user,'Password reset','Password reset; earlier sessions revoked');db.commit()
    return {'message':'Password updated. Earlier sessions are revoked. Sign in with your new password.'}


class NotificationPreference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool


@router.patch('/notifications')
def preferences(data:NotificationPreference,db:Database,user:CurrentUser):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    state=security_state(db,user);state.notifications_enabled=data.enabled;db.commit()
    return {'enabled':state.notifications_enabled}
