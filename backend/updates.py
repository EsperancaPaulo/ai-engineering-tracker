"""Personal updates generated from real project data while the tracker is checked."""
import hashlib
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,HTTPException,Response
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select,func,case,update
from auth import Database
from tracker import CurrentUser,project_access,public_task
from models import User,Project,Task,ProjectMember,InboxNotice,ProjectProgress,TaskReminder,NotificationSettings
router=APIRouter(prefix='/api',tags=['In-app updates'])


def notices(user_id):
    return select(InboxNotice).join(ProjectMember,ProjectMember.project_id==InboxNotice.project_id).where(InboxNotice.user_id==user_id,ProjectMember.user_id==user_id)


def lock_user(db,user):
    db.scalar(select(User.id).where(User.id==user.id).with_for_update())


def notice_once(db,user_id,project_id,task_id,message,key):
    digest=hashlib.sha256(key.encode()).hexdigest()
    if not db.scalar(select(InboxNotice.id).where(InboxNotice.event_key==digest)):
        db.add(InboxNotice(user_id=user_id,project_id=project_id,task_id=task_id,message=message,event_key=digest))


def materialize(db,user):
    # Serialize this user's baseline and reminder checks across tabs/processes.
    lock_user(db,user)
    settings=db.get(NotificationSettings,user.id)
    progress_enabled=settings.progress_enabled if settings else True
    counts=db.execute(select(Project.id,Project.name,func.count(Task.id),func.sum(case((Task.status=='done',1),else_=0))).join(ProjectMember,ProjectMember.project_id==Project.id).outerjoin(Task,Task.project_id==Project.id).where(ProjectMember.user_id==user.id).group_by(Project.id,Project.name))
    for pid,name,total,done in counts:
        done=int(done or 0);snapshot=db.get(ProjectProgress,(user.id,pid))
        if snapshot is None:
            db.add(ProjectProgress(user_id=user.id,project_id=pid,total=total,completed=done))
        elif snapshot.total!=total or snapshot.completed!=done:
            if progress_enabled:
                percent=round(done/total*100) if total else 0
                notice_once(db,user.id,pid,None,f'Project progress: {name} — {done} of {total} tasks completed ({percent}%).',f'progress:{user.id}:{pid}:{done}:{total}')
            snapshot.total=total;snapshot.completed=done
    now=datetime.now(timezone.utc)
    due=list(db.scalars(select(TaskReminder).where(TaskReminder.user_id==user.id,TaskReminder.delivered.is_(False)).order_by(TaskReminder.remind_at).limit(50)))
    for reminder in due:
        task=db.get(Task,reminder.task_id)
        member=db.get(ProjectMember,(task.project_id,user.id)) if task else None
        if task and member and task.status!='done':
            due_at=reminder.remind_at.replace(tzinfo=timezone.utc) if reminder.remind_at.tzinfo is None else reminder.remind_at.astimezone(timezone.utc)
            if due_at>now:continue
            stamp=reminder.remind_at.replace(tzinfo=timezone.utc) if reminder.remind_at.tzinfo is None else reminder.remind_at.astimezone(timezone.utc)
            notice_once(db,user.id,task.project_id,task.id,f'Reminder: {task.title}',f'reminder:{user.id}:{task.id}:{stamp.isoformat()}')
        reminder.delivered=True
    db.flush()


def kind(message):
    if message.startswith('Reminder: '):return 'reminder'
    if message.startswith('Project progress: '):return 'progress'
    return 'assignment'


def unread_count(db,user):
    return db.scalar(select(func.count()).select_from(notices(user.id).where(InboxNotice.read.is_(False)).subquery()))


@router.get('/updates/summary')
def summary(db:Database,user:CurrentUser):
    materialize(db,user)
    count=unread_count(db,user);db.commit()
    return {'unread_count':count}


@router.get('/updates')
def updates(db:Database,user:CurrentUser,cursor:int|None=None,unread:bool=False,category:Literal['all','assignment','reminder','progress']='all'):
    if cursor is not None and cursor<1:raise HTTPException(422,'Invalid updates page.')
    materialize(db,user)
    query=notices(user.id)
    if unread:query=query.where(InboxNotice.read.is_(False))
    if cursor:query=query.where(InboxNotice.id<cursor)
    if category=='reminder':query=query.where(InboxNotice.message.startswith('Reminder: '))
    elif category=='progress':query=query.where(InboxNotice.message.startswith('Project progress: '))
    elif category=='assignment':query=query.where(~InboxNotice.message.startswith('Reminder: '),~InboxNotice.message.startswith('Project progress: '))
    rows=list(db.scalars(query.order_by(InboxNotice.id.desc()).limit(26)));items=[]
    for row in rows[:25]:
        project=db.get(Project,row.project_id);task=db.get(Task,row.task_id) if row.task_id else None
        # Moved tasks may now belong to a project this recipient cannot read.
        available=bool(task and db.get(ProjectMember,(task.project_id,user.id)))
        items.append({'id':row.id,'message':row.message,'category':kind(row.message),'read':row.read,'created_at':row.created_at,'project_id':row.project_id,'project_name':project.name,'task_id':task.id if available else None})
    setting=db.get(NotificationSettings,user.id);count=unread_count(db,user);db.commit()
    return {'items':items,'next_cursor':rows[24].id if len(rows)>25 else None,'unread_count':count,'progress_enabled':setting.progress_enabled if setting else True}


class ReadState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    read:bool


@router.patch('/updates/{notice_id}')
def read_state(notice_id:int,data:ReadState,db:Database,user:CurrentUser):
    row=db.scalar(notices(user.id).where(InboxNotice.id==notice_id))
    if row is None:raise HTTPException(404,'Update not found.')
    row.read=data.read;db.commit();return {'read':row.read}


@router.post('/updates/read-all')
def read_all(db:Database,user:CurrentUser):
    ids=notices(user.id).with_only_columns(InboxNotice.id)
    db.execute(update(InboxNotice).where(InboxNotice.id.in_(ids)).values(read=True));db.commit()
    return {'unread_count':0}


class ProgressPreference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool


@router.patch('/update-preferences')
def preference(data:ProgressPreference,db:Database,user:CurrentUser):
    # Record current counts first; re-enabling does not replay old checkpoints.
    materialize(db,user)
    value=db.get(NotificationSettings,user.id)
    if not value:value=NotificationSettings(user_id=user.id);db.add(value)
    value.progress_enabled=data.enabled;db.commit();return {'progress_enabled':data.enabled}


def readable_task(db,user,task_id):
    task=db.get(Task,task_id)
    if not task:raise HTTPException(404,'Task not found.')
    _,role=project_access(db,user,task.project_id)
    return task,role


@router.get('/updates/tasks/{task_id}')
def open_task(task_id:int,db:Database,user:CurrentUser):
    task,role=readable_task(db,user,task_id)
    return public_task(db,task,user,role)


class ReminderInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    minutes:Literal[1,60,1440]


@router.post('/reminders/{task_id}')
def schedule(task_id:int,data:ReminderInput,db:Database,user:CurrentUser):
    lock_user(db,user);task,_=readable_task(db,user,task_id)
    if task.status=='done':raise HTTPException(409,'This task is completed. Reopen it before setting a reminder.')
    active=db.scalar(select(func.count()).select_from(TaskReminder).where(TaskReminder.user_id==user.id,TaskReminder.delivered.is_(False)))
    value=db.get(TaskReminder,(user.id,task_id))
    if active>=50 and (not value or value.delivered):raise HTTPException(409,'You have 50 active reminders. Cancel one before adding another.')
    if value is None:value=TaskReminder(user_id=user.id,task_id=task_id);db.add(value)
    value.remind_at=datetime.now(timezone.utc)+timedelta(minutes=data.minutes);value.delivered=False
    db.commit();return {'task_id':task_id,'remind_at':value.remind_at}


@router.get('/reminders')
def reminders(db:Database,user:CurrentUser):
    rows=db.execute(select(TaskReminder,Task,Project).join(Task,Task.id==TaskReminder.task_id).join(Project,Project.id==Task.project_id).join(ProjectMember,ProjectMember.project_id==Project.id).where(TaskReminder.user_id==user.id,TaskReminder.delivered.is_(False),Task.status!='done',ProjectMember.user_id==user.id).order_by(TaskReminder.remind_at).limit(50))
    return [{'task_id':task.id,'title':task.title,'project_name':project.name,'remind_at':reminder.remind_at} for reminder,task,project in rows]


@router.delete('/reminders/{task_id}',status_code=204)
def cancel(task_id:int,db:Database,user:CurrentUser):
    lock_user(db,user);readable_task(db,user,task_id)
    value=db.get(TaskReminder,(user.id,task_id))
    if value is None:raise HTTPException(404,'Reminder not found.')
    value.delivered=True;db.commit();return Response(status_code=204)
