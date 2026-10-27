import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select, delete
from sqlalchemy.exc import IntegrityError

from auth import Database, get_current_user
from models import ActivityLog, Project, ProjectMember, Task, User, AutomationRule, InboxNotice, SlackDelivery
from schemas import normalize_email

router = APIRouter(prefix='/api', tags=['Tracker'])
CurrentUser = Annotated[User, Depends(get_current_user)]


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default='', max_length=4000)

    @field_validator('name', mode='before')
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProjectOutput(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    description: str | None
    role: Literal['owner', 'editor', 'viewer']


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    project_id: int = Field(gt=0)
    priority: Literal['low', 'medium', 'high'] = 'medium'
    assigned_to: int | None = Field(default=None, gt=0)
    description: str = Field(default='', max_length=8000)

    @field_validator('title', mode='before')
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class TaskOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    project_id: int
    priority: str
    status: str
    assigned_to: int | None
    assignee_name: str | None
    description: str | None
    created_at: datetime
    can_edit: bool


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default=None, min_length=1, max_length=200)
    project_id: int = Field(default=None, gt=0)
    priority: Literal['low', 'medium', 'high'] = None
    status: Literal['todo', 'in_progress', 'done'] = None
    assigned_to: int = Field(default=None, gt=0)
    description: str = Field(default=None, max_length=8000)

    @field_validator('title', mode='before')
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class ActivityOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    details: str | None
    created_at: datetime


class MemberInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=255)
    role: Literal['editor', 'viewer'] = 'editor'

    @field_validator('email', mode='before')
    @classmethod
    def clean_email(cls, value):
        return normalize_email(value) if isinstance(value, str) else value


class MemberRole(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['editor', 'viewer']


class MemberOutput(BaseModel):
    user_id: int
    name: str
    role: str


def record(db, user, action, details):
    db.add(ActivityLog(user_id=user.id, action=action, details=details))


def project_access(db, user, project_id, write=False, owner_only=False):
    query = select(Project).where(Project.id == project_id)
    if write:
        query = query.with_for_update()
    project = db.scalar(query)
    member = db.get(ProjectMember, (project_id, user.id)) if project else None
    if member is None:
        raise HTTPException(404, 'Project not found')
    if (owner_only and member.role != 'owner') or (write and member.role == 'viewer'):
        raise HTTPException(403, 'Your project role does not allow this action')
    return project, member.role


def public_project(project, role):
    return {'id': project.id, 'name': project.name, 'description': project.description,
            'created_at': project.created_at, 'role': role}


def public_task(db, task, user, role):
    assignee = db.get(User, task.assigned_to) if task.assigned_to else None
    return {**{key: getattr(task, key) for key in ['id','title','project_id','priority','status','assigned_to','description','created_at']},
            'assignee_name': assignee.name if assignee else None,
            'can_edit': role == 'owner' or (role == 'editor' and task.assigned_to == user.id)}


def task_access(db, user, task_id):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Task not found')
    _, role = project_access(db, user, task.project_id, write=True)
    if role != 'owner' and task.assigned_to != user.id:
        raise HTTPException(403, 'Only the assignee or project owner can change this task')
    return task, role


def valid_assignee(db, project_id, user_id):
    member = db.get(ProjectMember, (project_id, user_id))
    if member is None or member.role == 'viewer':
        raise HTTPException(422, 'Choose an owner or editor who belongs to the destination project')


@router.get('/projects', response_model=list[ProjectOutput])
def projects(db: Database, user: CurrentUser):
    rows = db.execute(select(Project, ProjectMember.role).join(ProjectMember).where(ProjectMember.user_id == user.id).order_by(Project.created_at.desc(), Project.id.desc()))
    return [public_project(project, role) for project, role in rows]


@router.post('/projects', response_model=ProjectOutput, status_code=201)
def create_project(data: ProjectInput, db: Database, user: CurrentUser):
    project = Project(**data.model_dump())
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role='owner'))
    record(db, user, 'Project created', data.name)
    db.commit()
    db.refresh(project)
    return public_project(project, 'owner')


@router.get('/tasks', response_model=list[TaskOutput])
def tasks(db: Database, user: CurrentUser, scope: Literal['mine', 'team'] = 'mine'):
    query = select(Task, ProjectMember.role).join(ProjectMember, Task.project_id == ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    if scope == 'mine':
        query = query.where(Task.assigned_to == user.id)
    rows = db.execute(query.order_by(Task.created_at.desc(), Task.id.desc()))
    return [public_task(db, task, user, role) for task, role in rows]


@router.post('/tasks', response_model=TaskOutput, status_code=201)
def create_task(data: TaskInput, db: Database, user: CurrentUser):
    _, role = project_access(db, user, data.project_id, write=True)
    assignee = data.assigned_to or user.id
    if assignee != user.id and role != 'owner':
        raise HTTPException(403, 'Only the project owner can assign tasks to other members')
    valid_assignee(db, data.project_id, assignee)
    task = Task(**data.model_dump(exclude={'assigned_to'}), assigned_to=assignee, status='todo')
    db.add(task)
    db.flush()
    from workflows import notify_assignee
    notify_assignee(db,task,user.id)
    record(db, user, 'Task added', data.title)
    db.commit()
    db.refresh(task)
    return public_task(db, task, user, role)


@router.patch('/tasks/{task_id}', response_model=TaskOutput)
def update_task(task_id: int, data: TaskUpdate, db: Database, user: CurrentUser):
    task, role = task_access(db, user, task_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, 'Provide at least one field to update')
    destination = changes.get('project_id', task.project_id)
    destination_role = role
    if destination != task.project_id:
        _, destination_role = project_access(db, user, destination, write=True)
    assignee = changes.get('assigned_to', task.assigned_to)
    if 'assigned_to' in changes and assignee != task.assigned_to and (role != 'owner' or destination_role != 'owner'):
        raise HTTPException(403, 'Only a project owner can reassign tasks')
    if assignee is not None:
        valid_assignee(db, destination, assignee)
    before = {field: getattr(task, field) for field in changes}
    for field, value in changes.items():
        setattr(task, field, value)
    if ('assigned_to' in before and before['assigned_to']!=task.assigned_to) or ('priority' in before and before['priority']!=task.priority and task.priority=='high' and task.status!='done'):
        from workflows import notify_assignee
        notify_assignee(db,task,user.id)
    record(db, user, 'Task updated', json.dumps({'summary': f'{task.title}: {task.status}', 'task_id': task.id, 'before': before, 'after': changes}))
    db.commit()
    db.refresh(task)
    return public_task(db, task, user, destination_role)


@router.get('/activity', response_model=list[ActivityOutput])
def activity(db: Database, user: CurrentUser):
    return db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id).order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(20)).all()


@router.put('/projects/{project_id}', response_model=ProjectOutput)
def edit_project(project_id: int, data: ProjectInput, db: Database, user: CurrentUser):
    project, role = project_access(db, user, project_id, write=True)
    before = {'name': project.name, 'description': project.description}
    for field, value in data.model_dump().items():
        setattr(project, field, value)
    record(db, user, 'Project edited', json.dumps({'summary': project.name, 'project_id': project.id, 'before': before, 'after': data.model_dump()}))
    db.commit()
    db.refresh(project)
    return public_project(project, role)


@router.delete('/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, db: Database, user: CurrentUser):
    task, _ = task_access(db, user, task_id)
    record(db, user, 'Task deleted', json.dumps({'summary': task.title, 'task_id': task.id, 'before': {key: getattr(task,key) for key in ['title','project_id','priority','status','description','assigned_to']}}))
    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.delete('/projects/{project_id}', status_code=204)
def delete_project(project_id: int, db: Database, user: CurrentUser):
    project, _ = project_access(db, user, project_id, write=True, owner_only=True)
    if db.scalar(select(Task.id).where(Task.project_id == project_id).limit(1)) is not None:
        raise HTTPException(409, 'This project still has tasks. Move or delete them before deleting the project.')
    record(db, user, 'Project deleted', json.dumps({'summary': project.name, 'project_id': project.id, 'before': {'name': project.name, 'description': project.description}}))
    db.execute(delete(InboxNotice).where(InboxNotice.project_id==project_id))
    db.execute(delete(SlackDelivery).where(SlackDelivery.project_id==project_id))
    db.execute(delete(AutomationRule).where(AutomationRule.project_id == project_id))
    db.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
    db.delete(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'The project is still in use. Refresh and try again.') from None
    return Response(status_code=204)


@router.get('/projects/{project_id}/members', response_model=list[MemberOutput])
def members(project_id: int, db: Database, user: CurrentUser):
    project_access(db, user, project_id)
    return [{'user_id':member.user_id,'name':name,'role':member.role} for member,name in db.execute(select(ProjectMember,User.name).join(User,ProjectMember.user_id == User.id).where(ProjectMember.project_id == project_id).order_by(ProjectMember.created_at,ProjectMember.user_id))]


@router.post('/projects/{project_id}/members', response_model=MemberOutput, status_code=201)
def add_member(project_id: int, data: MemberInput, db: Database, user: CurrentUser):
    project, _ = project_access(db, user, project_id, write=True, owner_only=True)
    target = db.scalar(select(User).where(func.lower(User.email) == normalize_email(str(data.email))))
    if target is None:
        raise HTTPException(404, 'No registered account found. Ask this person to create an account first.')
    if db.get(ProjectMember, (project_id, target.id)):
        raise HTTPException(409, 'This account already belongs to the project')
    db.add(ProjectMember(project_id=project_id, user_id=target.id, role=data.role))
    record(db, user, 'Member added', json.dumps({'summary': f'{target.name} joined {project.name} as {data.role}', 'project_id':project_id, 'member_id':target.id, 'role':data.role}))
    db.commit()
    return {'user_id':target.id,'name':target.name,'role':data.role}


@router.put('/projects/{project_id}/members/{member_id}', response_model=MemberOutput)
def change_member(project_id: int, member_id: int, data: MemberRole, db: Database, user: CurrentUser):
    project, _ = project_access(db, user, project_id, write=True, owner_only=True)
    member = db.get(ProjectMember,(project_id,member_id))
    if member is None:
        raise HTTPException(404, 'Member not found')
    if member.role == 'owner':
        raise HTTPException(409, 'The project owner cannot be changed here')
    before = member.role
    member.role = data.role
    target = db.get(User,member_id)
    record(db,user,'Member role changed',json.dumps({'summary':f'{target.name}: {before} → {data.role}', 'project_id':project.id,'member_id':member_id,'before':before,'after':data.role}))
    db.commit()
    return {'user_id':member_id,'name':target.name,'role':data.role}


@router.delete('/projects/{project_id}/members/{member_id}', status_code=204)
def remove_member(project_id: int, member_id: int, db: Database, user: CurrentUser):
    project, _ = project_access(db, user, project_id, write=True, owner_only=True)
    member = db.get(ProjectMember,(project_id,member_id))
    if member is None:
        raise HTTPException(404, 'Member not found')
    if member.role == 'owner':
        raise HTTPException(409, 'The project owner cannot be removed')
    if db.scalar(select(Task.id).where(Task.project_id == project_id,Task.assigned_to == member_id).limit(1)) is not None:
        raise HTTPException(409, 'Reassign this member’s tasks before removing them')
    target = db.get(User,member_id)
    record(db,user,'Member removed',json.dumps({'summary':f'{target.name} left {project.name}','project_id':project.id,'member_id':member_id,'before':member.role}))
    db.delete(member)
    db.commit()
    return Response(status_code=204)
