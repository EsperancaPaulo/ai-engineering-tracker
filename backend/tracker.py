import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from auth import Database, get_current_user
from models import ActivityLog, Project, Task, User

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


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    project_id: int = Field(gt=0)
    priority: Literal['low', 'medium', 'high'] = 'medium'

    @field_validator('title', mode='before')
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class TaskOutput(TaskInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default=None, min_length=1, max_length=200)
    project_id: int = Field(default=None, gt=0)
    priority: Literal['low', 'medium', 'high'] = None
    status: Literal['todo', 'in_progress', 'done'] = None

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


def record(db, user, action, details):
    db.add(ActivityLog(user_id=user.id, action=action, details=details))


@router.get('/projects', response_model=list[ProjectOutput])
def projects(db: Database, user: CurrentUser):
    return db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())).all()


@router.post('/projects', response_model=ProjectOutput, status_code=201)
def create_project(data: ProjectInput, db: Database, user: CurrentUser):
    project = Project(**data.model_dump())
    db.add(project)
    record(db, user, 'Project created', data.name)
    db.commit()
    db.refresh(project)
    return project


@router.get('/tasks', response_model=list[TaskOutput])
def tasks(db: Database, user: CurrentUser):
    return db.scalars(select(Task).where(Task.assigned_to == user.id).order_by(Task.created_at.desc(), Task.id.desc())).all()


@router.post('/tasks', response_model=TaskOutput, status_code=201)
def create_task(data: TaskInput, db: Database, user: CurrentUser):
    if db.get(Project, data.project_id) is None:
        raise HTTPException(404, 'Project not found')
    task = Task(**data.model_dump(), assigned_to=user.id, status='todo')
    db.add(task)
    record(db, user, 'Task added', data.title)
    db.commit()
    db.refresh(task)
    return task


@router.patch('/tasks/{task_id}', response_model=TaskOutput)
def update_task(task_id: int, data: TaskUpdate, db: Database, user: CurrentUser):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.assigned_to == user.id))
    if task is None:
        raise HTTPException(404, 'Task not found')
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, 'Provide at least one field to update')
    if 'project_id' in changes and db.get(Project, changes['project_id']) is None:
        raise HTTPException(404, 'Project not found')
    before = {field: getattr(task, field) for field in changes}
    for field, value in changes.items():
        setattr(task, field, value)
    record(db, user, 'Task updated', json.dumps({
        'summary': f'{task.title}: {task.status}', 'task_id': task.id,
        'before': before, 'after': changes,
    }))
    db.commit()
    db.refresh(task)
    return task


@router.get('/activity', response_model=list[ActivityOutput])
def activity(db: Database, user: CurrentUser):
    return db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id).order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(20)).all()


@router.put('/projects/{project_id}', response_model=ProjectOutput)
def edit_project(project_id: int, data: ProjectInput, db: Database, user: CurrentUser):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    before = {'name': project.name, 'description': project.description}
    for field, value in data.model_dump().items():
        setattr(project, field, value)
    record(db, user, 'Project edited', json.dumps({
        'summary': project.name, 'project_id': project.id,
        'before': before, 'after': data.model_dump(),
    }))
    db.commit()
    db.refresh(project)
    return project


@router.delete('/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, db: Database, user: CurrentUser):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.assigned_to == user.id))
    if task is None:
        raise HTTPException(404, 'Task not found')
    record(db, user, 'Task deleted', json.dumps({
        'summary': task.title, 'task_id': task.id,
        'before': {'title': task.title, 'project_id': task.project_id,
                   'priority': task.priority, 'status': task.status,
                   'description': task.description},
    }))
    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.delete('/projects/{project_id}', status_code=204)
def delete_project(project_id: int, db: Database, user: CurrentUser):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    # Check ALL tasks, including those assigned to other users or unassigned.
    if db.scalar(select(Task.id).where(Task.project_id == project_id).limit(1)) is not None:
        raise HTTPException(409, 'This shared project still has tasks. Move or delete them before deleting the project; other members may have tasks here.')
    record(db, user, 'Project deleted', json.dumps({
        'summary': project.name, 'project_id': project.id,
        'before': {'name': project.name, 'description': project.description},
    }))
    db.delete(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'The project is still in use. Refresh and try again.') from None
    return Response(status_code=204)
