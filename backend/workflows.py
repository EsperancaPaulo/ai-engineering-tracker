"""Local reports, assignee inbox and explicitly approved Slack messages."""
import csv,hashlib,io,json,os,re
from datetime import datetime,timedelta,timezone
from typing import Literal
import httpx,jwt
from fastapi import APIRouter,HTTPException,Response
from pydantic import BaseModel,ConfigDict,SecretStr,Field
from sqlalchemy import select
from auth import ALGORITHM,ISSUER,SECRET_KEY,Database
from tracker import CurrentUser,project_access,record
from models import Task,User,Project,ProjectMember,ActivityLog,InboxNotice,SlackDelivery,UserSecurity
router=APIRouter(prefix='/api',tags=['Reports and notifications'])


def notify_assignee(db,task,actor_id):
    if not task.assigned_to or task.assigned_to==actor_id:return
    preference=db.get(UserSecurity,task.assigned_to)
    if preference and not preference.notifications_enabled:return
    key=hashlib.sha256(f'{task.id}:{task.assigned_to}:{task.priority}:{task.status}:{task.title}'.encode()).hexdigest()
    if db.scalar(select(InboxNotice.id).where(InboxNotice.event_key==key)):return
    label='High-priority task assigned' if task.priority=='high' else 'Task assigned'
    db.add(InboxNotice(project_id=task.project_id,user_id=task.assigned_to,task_id=task.id,event_key=key,message=f'{label}: {task.title}'))


@router.get('/inbox')
def inbox(db:Database,user:CurrentUser):
    rows=db.scalars(select(InboxNotice).join(ProjectMember,ProjectMember.project_id==InboxNotice.project_id).where(InboxNotice.user_id==user.id,ProjectMember.user_id==user.id).order_by(InboxNotice.id.desc()).limit(100))
    return [{'id':row.id,'message':row.message,'read':row.read,'created_at':row.created_at} for row in rows]


@router.patch('/inbox/{notice_id}/read',status_code=204)
def read_notice(notice_id:int,db:Database,user:CurrentUser):
    notice=db.get(InboxNotice,notice_id)
    if not notice or notice.user_id!=user.id:raise HTTPException(404,'Notification not found')
    project_access(db,user,notice.project_id)
    notice.read=True;db.commit();return Response(status_code=204)


@router.get('/projects/{project_id}/report')
def report(project_id:int,db:Database,user:CurrentUser):
    project_access(db,user,project_id)
    tasks=list(db.scalars(select(Task).where(Task.project_id==project_id)))
    counts={key:sum(task.status==key for task in tasks) for key in ('todo','in_progress','done')}
    imports,automated=set(),set()
    for action,details in db.execute(select(ActivityLog.action,ActivityLog.details).where(ActivityLog.action.in_(['File task imported','GitHub issue imported','Automation applied']))):
        try:
            value=json.loads(details)
            if value.get('project_id')!=project_id:continue
            (automated if action=='Automation applied' else imports).add(value['task_id'])
        except (ValueError,TypeError,KeyError):continue
    return {'total_tasks':len(tasks),'statuses':counts,'high_priority_open':sum(task.priority=='high' and task.status!='done' for task in tasks),'imported_tasks_history':len(imports),'automated_tasks_history':len(automated),'completion_percent':round(counts['done']/len(tasks)*100) if tasks else 0}


@router.get('/projects/{project_id}/export')
def export(project_id:int,db:Database,user:CurrentUser):
    project_access(db,user,project_id)
    rows=list(db.scalars(select(Task).where(Task.project_id==project_id).order_by(Task.id).limit(10001)))
    if len(rows)>10000:raise HTTPException(422,'Export supports up to 10,000 tasks per project.')
    def safe(value):
        text=str(value or '')
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r')) else text
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['title','description','priority','status','assignee'])
    for task in rows:
        person=db.get(User,task.assigned_to) if task.assigned_to else None
        writer.writerow([safe(task.title),safe(task.description),task.priority,task.status,safe(person.name if person else '')])
    return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="project-tasks.csv"'})


def slack_settings(project_id):
    url=os.getenv('SLACK_WEBHOOK_URL','').strip()
    valid=bool(re.fullmatch(r'https://hooks\.slack\.com/services/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+',url))
    ready=valid and bool(os.getenv('SLACK_CHANNEL_LABEL','').strip()) and os.getenv('SLACK_PROJECT_ID','')==str(project_id)
    return url,{'ready':ready,'sending_enabled':ready and os.getenv('SLACK_SENDING_ENABLED','false').lower()=='true','destination':os.getenv('SLACK_CHANNEL_LABEL','Configured Slack channel')[:100]}


@router.get('/projects/{project_id}/integrations')
def integrations(project_id:int,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    return {'slack':slack_settings(project_id)[1],'project_id':project_id}


class MessagePreview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['urgent','summary']='urgent'


class MessageSend(BaseModel):
    model_config=ConfigDict(extra='forbid')
    preview_token:SecretStr = Field(max_length=30000)
    confirmed:Literal[True]


def message(db,project_id,kind):
    project=db.get(Project,project_id)
    query=select(Task).where(Task.project_id==project_id)
    if kind=='urgent':query=query.where(Task.priority=='high',Task.status!='done')
    tasks=list(db.scalars(query.order_by(Task.id.desc()).limit(10)))
    lines=[f'AI Engineering Tracker — {project.name}', 'High-priority open tasks' if kind=='urgent' else 'Latest task summary']
    for task in tasks:
        person=db.get(User,task.assigned_to) if task.assigned_to else None
        lines.append(f'• {task.title} | {task.priority} | {task.status} | {person.name if person else "Unassigned"}')
    if not tasks:lines.append('No matching tasks.')
    # Plain-text blocks plus escaped fallback avoid mentions, markup and link unfurls.
    return '\n'.join(lines).replace('@','@\u200b')[:2800]


@router.post('/projects/{project_id}/slack/preview')
def slack_preview(project_id:int,data:MessagePreview,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    url,config=slack_settings(project_id)
    if not config['ready']:raise HTTPException(503,'Configure a Slack webhook, channel label and this project binding first.')
    text=message(db,project_id,data.kind);target=hashlib.sha256(url.encode()).hexdigest()
    key=hashlib.sha256((str(project_id)+target+text).encode()).hexdigest()
    now=datetime.now(timezone.utc)
    token=jwt.encode({'iss':ISSUER+'/slack-preview','sub':str(user.id),'aud':str(project_id),'iat':now,'exp':now+timedelta(minutes=5),'text':text,'kind':data.kind,'target':target,'key':key},SECRET_KEY,algorithm=ALGORITHM)
    existing=db.scalar(select(SlackDelivery).where(SlackDelivery.delivery_key==key))
    return {'text':text,'destination':config['destination'],'preview_token':token,'sending_enabled':config['sending_enabled'],'already_attempted':existing is not None}


@router.post('/projects/{project_id}/slack/send')
def slack_send(project_id:int,data:MessageSend,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    url,config=slack_settings(project_id)
    if not config['sending_enabled']:raise HTTPException(503,'Slack sending is disabled. Preview is available once configured.')
    try:
        claims=jwt.decode(data.preview_token.get_secret_value(),SECRET_KEY,algorithms=[ALGORITHM],issuer=ISSUER+'/slack-preview',audience=str(project_id),options={'require':['sub','aud','iss','iat','exp','text','target','key','kind']})
        if claims['sub']!=str(user.id) or claims['target']!=hashlib.sha256(url.encode()).hexdigest() or claims['text']!=message(db,project_id,claims['kind']):raise ValueError()
    except (jwt.InvalidTokenError,ValueError,KeyError,TypeError):raise HTTPException(422,'Slack preview expired or changed. Preview again.') from None
    if db.scalar(select(SlackDelivery.id).where(SlackDelivery.delivery_key==claims['key'])):raise HTTPException(409,'This update was already attempted. Check the channel before preparing another update.')
    delivery=SlackDelivery(project_id=project_id,user_id=user.id,delivery_key=claims['key'],state='sending')
    db.add(delivery);db.commit();delivery_id=delivery.id
    try:
        with httpx.Client(timeout=httpx.Timeout(10,connect=4),follow_redirects=False,trust_env=False) as client:
            response=client.post(url,json={'text':claims['text'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'),'blocks':[{'type':'section','text':{'type':'plain_text','text':claims['text'],'emoji':False}}],'unfurl_links':False,'unfurl_media':False})
        state='sent' if response.status_code==200 and response.text.strip()=='ok' else 'failed'
    except httpx.HTTPError:state='uncertain'
    delivery=db.get(SlackDelivery,delivery_id);delivery.state=state
    record(db,user,'Slack update '+state,json.dumps({'summary':'Reviewed '+claims['kind']+' update: '+state,'project_id':project_id,'delivery_id':delivery_id}))
    db.commit()
    if state!='sent':raise HTTPException(502,'Slack delivery was not confirmed. Check the channel; this update will not be retried automatically to prevent duplicate messages.')
    return {'state':'sent'}


@router.get('/projects/{project_id}/tasks-page')
def task_page(project_id:int,db:Database,user:CurrentUser,cursor:int|None=None,limit:int=25,q:str='',status:Literal['todo','in_progress','done']|None=None):
    _,role=project_access(db,user,project_id)
    if not 1<=limit<=100 or (cursor is not None and cursor<1) or len(q)>100:raise HTTPException(422,'Choose a page size from 1–100 and a search up to 100 characters.')
    query=select(Task).where(Task.project_id==project_id)
    if cursor is not None:query=query.where(Task.id<cursor)
    if q:
        literal=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(Task.title.ilike('%'+literal+'%',escape='\\'))
    if status:query=query.where(Task.status==status)
    rows=list(db.scalars(query.order_by(Task.id.desc()).limit(limit+1)))
    from tracker import public_task
    return {'items':[public_task(db,row,user,role) for row in rows[:limit]],'next_cursor':rows[limit-1].id if len(rows)>limit else None}
