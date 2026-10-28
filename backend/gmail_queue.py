"""Durable Gmail drafts; collecting never writes tasks or changes the mailbox."""
import hashlib,json
from datetime import datetime,timedelta,timezone
from typing import Literal
import jwt
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field,SecretStr
from sqlalchemy import select,func
from auth import Database,SECRET_KEY,ALGORITHM,ISSUER
from tracker import CurrentUser,project_access,record
from models import GmailSource,GmailDraft,Task,User
from file_imports import parse_email,fingerprint,existing_fingerprints
import automation,gmail_client
router=APIRouter(prefix='/api/projects/{project_id}/gmail',tags=['Gmail review queue'])
PREVIEW_ISSUER=ISSUER+'/gmail-review'


def source_access(db,user,project_id,write=False):
    project_access(db,user,project_id,write=write,owner_only=True)
    source=db.scalar(select(GmailSource).where(GmailSource.project_id==project_id).execution_options(populate_existing=True))
    if not source or source.owner_id!=user.id:raise HTTPException(503,'Gmail is not connected to this project. Use the private local connection tool first.')
    return source


def utc(value):return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def collect(db,user,project_id,automatic_only=False):
    source=source_access(db,user,project_id,write=True)
    if automatic_only and not source.automatic:raise HTTPException(409,'Automatic collection is paused.')
    now=datetime.now(timezone.utc)
    if source.next_poll and utc(source.next_poll)>now:raise HTTPException(429,'Gmail collection is waiting. Please try again after the collection interval.')
    pending_count=db.scalar(select(func.count()).select_from(GmailDraft).where(GmailDraft.project_id==project_id,GmailDraft.state=='pending'))
    if pending_count>=100:
        raise HTTPException(409,'Review or dismiss pending email drafts before collecting more (limit 100).')
    try:messages,cursor=gmail_client.read_page(project_id,user.id,source.account_key,source.label_id,source.cursor)
    except HTTPException:
        source.failures+=1;source.next_poll=now+timedelta(seconds=min(3600,60*2**min(source.failures,6)));source.last_result='Collection failed; waiting before retry. Reconnect if access expired.';db.commit();raise
    added=0
    for key,raw,problem in messages:
        if pending_count>=100:
            cursor=source.cursor
            break
        if db.scalar(select(GmailDraft.id).where(GmailDraft.message_key==key)):continue
        title=description=''
        if not problem:
            try:
                rows,_=parse_email(raw);title=rows[0]['title'];description=rows[0]['description']
            except HTTPException:problem='Email lacks a supported subject/body or exceeds import limits. Use a saved .eml file after correcting it.'
        db.add(GmailDraft(project_id=project_id,owner_id=user.id,message_key=key,title=title,description=description,state='blocked' if problem else 'pending',problem=problem));added+=1
        if not problem:pending_count+=1
    source.cursor=cursor;source.failures=0;source.next_poll=now+timedelta(seconds=60);source.last_result=f'{added} new email draft(s) collected; '+('more pages remain.' if cursor else 'scan complete.')
    record(db,user,'Gmail collected',json.dumps({'summary':source.last_result,'project_id':project_id,'draft_count':added}))
    db.commit();return {'collected_count':added,'more_pages':bool(cursor)}


@router.get('')
def status(project_id:int,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    source=db.get(GmailSource,project_id)
    connected=bool(source and source.owner_id==user.id)
    return {'connected':connected,'project_id':project_id,'owner_id':user.id,'label':gmail_client.LABEL,'automatic':source.automatic if connected else False,'last_result':source.last_result if connected else 'Not connected.','next_poll':source.next_poll if connected else None}


@router.post('/collect')
def collect_now(project_id:int,db:Database,user:CurrentUser):return collect(db,user,project_id)


@router.get('/drafts')
def drafts(project_id:int,db:Database,user:CurrentUser,cursor:int|None=None,state:Literal['pending','dismissed']='pending'):
    project_access(db,user,project_id,owner_only=True)
    query=select(GmailDraft).where(GmailDraft.project_id==project_id,GmailDraft.owner_id==user.id,GmailDraft.state.in_(['pending','blocked'] if state=='pending' else ['dismissed']))
    if cursor is not None:
        if cursor<1:raise HTTPException(422,'Invalid queue page.')
        query=query.where(GmailDraft.id<cursor)
    rows=list(db.scalars(query.order_by(GmailDraft.id.desc()).limit(26)))
    return {'items':[{'id':r.id,'title':r.title or 'Unsupported email','description':r.description,'state':r.state,'problem':r.problem} for r in rows[:25]],'next_cursor':rows[24].id if len(rows)>25 else None}


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    draft_ids:list[int]=Field(min_length=1,max_length=10)


@router.post('/preview')
def preview(project_id:int,data:Selection,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    ids=list(dict.fromkeys(data.draft_ids));rows=list(db.scalars(select(GmailDraft).where(GmailDraft.id.in_(ids),GmailDraft.project_id==project_id,GmailDraft.owner_id==user.id,GmailDraft.state=='pending')))
    if len(rows)!=len(ids):raise HTTPException(422,'Selected drafts changed or are unavailable. Reload the email queue.')
    rules=automation.rule_set(db,project_id);existing=existing_fingerprints(db,project_id);output=[]
    for row in rows:
        task={'title':row.title,'description':row.description,'priority':'medium'}
        output.append({'id':row.id,**task,'fingerprint':fingerprint(task),'automation':automation.effects(db,project_id,rules,row.title,row.description),'duplicate':fingerprint(task) in existing})
    now=datetime.now(timezone.utc)
    token=jwt.encode({'iss':PREVIEW_ISSUER,'aud':str(project_id),'sub':str(user.id),'iat':now,'exp':now+timedelta(minutes=5),'rows':output,'rule_digest':automation.digest(rules)},SECRET_KEY,algorithm=ALGORITHM)
    return {'rows':output,'preview_token':token}


class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    preview_token:SecretStr=Field(max_length=2000000)
    confirmed:Literal[True]


@router.post('/import')
def approve(project_id:int,data:Approval,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    try:
        claims=jwt.decode(data.preview_token.get_secret_value(),SECRET_KEY,algorithms=[ALGORITHM],issuer=PREVIEW_ISSUER,audience=str(project_id),options={'require':['sub','aud','iss','iat','exp','rows','rule_digest']})
        if claims['sub']!=str(user.id):raise ValueError()
    except (jwt.InvalidTokenError,ValueError,TypeError):raise HTTPException(422,'Email review expired or is invalid. Preview again.') from None
    automation.check_snapshot(db,project_id,claims['rule_digest'])
    existing=existing_fingerprints(db,project_id);created=skipped=0
    for row in claims['rows']:
        draft=db.get(GmailDraft,row['id'])
        if not draft or draft.project_id!=project_id or draft.owner_id!=user.id or draft.state!='pending':raise HTTPException(409,'Email drafts already processed or changed. Reload the queue.')
        if draft.title!=row['title'] or draft.description!=row['description']:raise HTTPException(409,'Email draft changed. Preview again.')
        if row['fingerprint'] in existing:
            draft.state='duplicate';skipped+=1
        else:
            task=Task(project_id=project_id,assigned_to=user.id,title=row['title'],description=row['description'],priority='medium',status='todo');db.add(task);db.flush()
            automation.apply(db,user,project_id,task,row['automation'],'gmail')
            record(db,user,'File task imported',json.dumps({'summary':'Reviewed Gmail task: '+task.title,'source':'gmail','project_id':project_id,'task_id':task.id,'fingerprint':row['fingerprint'],'draft_id':draft.id}))
            existing.add(row['fingerprint']);draft.state='imported';created+=1
        # Keep receipt, not a second copy of private content, after processing.
        draft.title='';draft.description=''
    db.commit();return {'imported_count':created,'skipped_count':skipped}


class QueueAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['dismiss','restore']


@router.patch('/drafts/{draft_id}')
def dismiss(project_id:int,draft_id:int,data:QueueAction,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    draft=db.get(GmailDraft,draft_id)
    if not draft or draft.project_id!=project_id or draft.owner_id!=user.id:raise HTTPException(404,'Email draft not found.')
    if data.action=='dismiss' and draft.state=='pending':draft.state='dismissed'
    elif data.action=='restore' and draft.state=='dismissed':draft.state='pending'
    else:raise HTTPException(409,'This draft cannot use that action.')
    db.commit();return {'state':draft.state}


class Automatic(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool


@router.patch('/automatic')
def automatic(project_id:int,data:Automatic,db:Database,user:CurrentUser):
    source=source_access(db,user,project_id,write=True);source.automatic=data.enabled;db.commit()
    return {'automatic':source.automatic}
