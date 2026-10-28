"""Optional local polling process; creates owner-only drafts, never tasks or sent emails."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
from database import SessionLocal
from models import GmailSource,User
from sqlalchemy import select
from gmail_queue import collect
from fastapi import HTTPException

def tick():
    with SessionLocal() as db:projects=list(db.scalars(select(GmailSource.project_id).where(GmailSource.automatic.is_(True))))
    for project_id in projects:
        with SessionLocal() as db:
            source=db.get(GmailSource,project_id)
            if not source or not source.automatic:continue
            user=db.get(User,source.owner_id)
            if not user:continue
            try:collect(db,user,project_id,automatic_only=True)
            except HTTPException:db.rollback()
            except Exception:
                db.rollback();print('Gmail worker paused this attempt due to a local error; inspect configuration without sharing logs or secrets.')

if __name__=='__main__':
    print('Gmail polling active for projects explicitly enabled in the app. Keep this process running; stopping it pauses polling. No AI or outbound messages.')
    try:
        while True:tick();time.sleep(60)
    except KeyboardInterrupt:print('Gmail polling stopped.')
