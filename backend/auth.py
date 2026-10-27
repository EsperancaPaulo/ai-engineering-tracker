import os
import hashlib,secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy import func, select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, RevokedSession, UserSecurity
from schemas import PublicUser, Registration, Token, normalize_email
from human_verification import require_human, public_settings
from password_policy import POLICY

# database imports load the backend's .env before settings are read.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if len(SECRET_KEY.encode()) < 32 or SECRET_KEY.lower().startswith(("change", "replace")):
    raise RuntimeError("Set JWT_SECRET_KEY to a random secret of at least 32 bytes")
TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
if not 1 <= TOKEN_MINUTES <= 60:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 60")
ALGORITHM = "HS256"
ISSUER = "ai-engineering-tracker"
password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing-only")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
router = APIRouter(tags=["Authentication"])


def get_db():
    with SessionLocal() as db:
        yield db


Database = Annotated[Session, Depends(get_db)]


def unauthorized():
    return HTTPException(status_code=401, detail="Invalid credentials or token", headers={"WWW-Authenticate": "Bearer"})


def create_access_token(user_id: int, version: int=0) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES), "iss": ISSUER, "jti":secrets.token_urlsafe(24), "ver":version}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Database):
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], issuer=ISSUER, options={"require": ["sub", "exp", "iat", "iss"]})
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdigit() or len(subject) > 19:
            raise unauthorized()
        user_id = int(subject)
        if not 0 < user_id <= 2147483647:
            raise unauthorized()
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized() from None
    if db.get(RevokedSession,hashlib.sha256(token.encode()).hexdigest()) is not None:
        raise unauthorized()
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized()
    security=db.get(UserSecurity,user.id)
    if claims.get("ver",0)!=(security.session_version if security else 0):raise unauthorized()
    return user


@router.post("/auth/register", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def register(data: Registration, db: Database, human=Depends(require_human)):
    email = normalize_email(str(data.email))
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(name=data.name, email=email, password_hash=password_hasher.hash(data.password.get_secret_value()), role="developer")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from None
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=Token)
def login(request:Request,response: Response, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Database):
    from account_email import limit
    limit('login:'+str(request.client.host if request.client else 'unknown'),20,60)
    # OAuth2 calls the email field 'username'. Bound work before database/hash operations.
    if len(form.username) > 255 or not 1 <= len(form.password) <= 128:
        raise unauthorized()
    user = db.scalar(select(User).where(func.lower(User.email) == normalize_email(form.username)).with_for_update())
    valid = password_hasher.verify(form.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise unauthorized()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    security=db.get(UserSecurity,user.id)
    if os.getenv('REQUIRE_VERIFIED_EMAIL','false').lower()=='true' and not (security and security.email_verified_at):
        raise HTTPException(403,'Verify your email before signing in. Use Forgot password, then choose Email verification to request a link.')
    return Token(access_token=create_access_token(user.id,security.session_version if security else 0), expires_in=TOKEN_MINUTES * 60)


@router.get("/me", response_model=PublicUser)
def me(response: Response, user: Annotated[User, Depends(get_current_user)]):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get('/auth/config')
def registration_config():
    return {'password_policy': POLICY, 'human_verification': public_settings()}


@router.post('/auth/logout',status_code=204)
def logout(token:Annotated[str,Depends(oauth2_scheme)],user:Annotated[User,Depends(get_current_user)],db:Database):
    claims=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM],issuer=ISSUER)
    db.execute(delete(RevokedSession).where(RevokedSession.expires_at<datetime.now(timezone.utc)))
    db.add(RevokedSession(token_digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=datetime.fromtimestamp(claims['exp'],timezone.utc)))
    try:db.commit()
    except IntegrityError:db.rollback()
    return Response(status_code=204)
