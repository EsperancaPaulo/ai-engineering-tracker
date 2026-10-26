"""Read public GitHub issues; import only owner-approved signed previews. Never write to GitHub."""
import json
import re
from datetime import datetime,timedelta,timezone
from typing import Annotated
import httpx
import jwt
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field,SecretStr,field_validator
from sqlalchemy import select
from auth import ALGORITHM,ISSUER,SECRET_KEY,Database
from models import ActivityLog,Task
from tracker import CurrentUser,project_access,record

router=APIRouter(prefix='/api/projects',tags=['GitHub imports'])
PREVIEW_ISSUER=ISSUER+'/github-preview'
REPOSITORY=re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}\Z')


class PreviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    repository:str=Field(min_length=3,max_length=140)
    page:int=Field(default=1,ge=1,le=100)
    @field_validator('repository')
    @classmethod
    def valid_repository(cls,value):
        value=value.strip()
        if not REPOSITORY.fullmatch(value) or value.split('/')[1] in ('.','..'):
            raise ValueError('Use owner/repository, without URLs or credentials')
        return value


class ImportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    preview_token:SecretStr=Field(min_length=1,max_length=250000)
    issue_numbers:list[Annotated[int,Field(gt=0)]]=Field(min_length=1,max_length=10)


def fetch_issues(repository,page):
    for attempt in range(2):
        try:
            with httpx.Client(timeout=httpx.Timeout(10,connect=4),follow_redirects=False,trust_env=False) as client:
                response=client.get(f'https://api.github.com/repos/{repository}/issues',params={'state':'open','per_page':20,'page':page,'sort':'created','direction':'desc'},headers={'Accept':'application/vnd.github+json','User-Agent':'AI-Engineering-Tracker'})
        except httpx.HTTPError:
            if attempt==0:continue
            raise HTTPException(502,'GitHub could not be reached. Please retry the preview.') from None
        if response.status_code>=500 and attempt==0:continue
        break
    if response.status_code==404:raise HTTPException(404,'Public repository not found or issues are unavailable. Private repositories are not supported yet.')
    if response.status_code in (403,429):raise HTTPException(429,'GitHub access or rate limit reached. Wait before trying again.',headers={'Retry-After':'60'})
    if response.status_code!=200:raise HTTPException(502,'GitHub could not return these issues. Confirm the repository name and try again.')
    try:
        rows=response.json()
        if not isinstance(rows,list) or len(rows)>20:raise ValueError()
        issues=[];remaining=100000
        for row in rows:
            if 'pull_request' in row:continue
            if not isinstance(row.get('id'),int) or not isinstance(row.get('number'),int) or not isinstance(row.get('title'),str):raise ValueError()
            number=row['number']
            body=str(row.get('body') or '')[:6000].encode('utf-8')[:remaining].decode('utf-8',errors='ignore')
            remaining-=len(body.encode('utf-8'))
            issues.append({'id':row['id'],'number':number,'title':row['title'][:200],
                           'body':body,
                           'url':f'https://github.com/{repository}/issues/{number}'})
    except (ValueError,TypeError,KeyError):raise HTTPException(502,'GitHub returned an unreadable response. Please try again.') from None
    return issues, 'rel="next"' in response.headers.get('link','')


def imported_ids(db,project_id):
    ids=set()
    for details in db.scalars(select(ActivityLog.details).where(ActivityLog.action=='GitHub issue imported')):
        try:
            value=json.loads(details)
            if value.get('project_id')==project_id:ids.add(value['github_issue_id'])
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return ids


@router.post('/{project_id}/github/preview')
def preview(project_id:int,data:PreviewInput,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    issues,next_page=fetch_issues(data.repository,data.page)
    existing=imported_ids(db,project_id)
    now=datetime.now(timezone.utc)
    token=jwt.encode({'iss':PREVIEW_ISSUER,'sub':str(user.id),'aud':str(project_id),'iat':now,'exp':now+timedelta(minutes=5),
                      'repository':data.repository,'issues':issues},SECRET_KEY,algorithm=ALGORITHM)
    return {'repository':data.repository,'page':data.page,'has_next':next_page,'preview_token':token,
            'issues':[{**issue,'already_imported':issue['id'] in existing} for issue in issues]}


@router.post('/{project_id}/github/import')
def import_selected(project_id:int,data:ImportInput,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    try:
        claims=jwt.decode(data.preview_token.get_secret_value(),SECRET_KEY,algorithms=[ALGORITHM],issuer=PREVIEW_ISSUER,audience=str(project_id),options={'require':['exp','iat','sub','aud','iss']})
        if claims['sub']!=str(user.id):raise ValueError()
        issues={issue['number']:issue for issue in claims['issues']}
        selected=list(dict.fromkeys(data.issue_numbers))
        if any(number not in issues for number in selected):raise ValueError()
    except (jwt.InvalidTokenError,ValueError,KeyError,TypeError):
        raise HTTPException(422,'Preview expired or does not match this import. Preview the repository again.') from None
    existing=imported_ids(db,project_id)
    created,skipped=[],[]
    for number in selected:
        issue=issues[number]
        if issue['id'] in existing:skipped.append(number);continue
        task=Task(title=issue['title'],description=issue['body']+'\n\nSource: '+issue['url'],project_id=project_id,assigned_to=user.id,status='todo',priority='medium')
        db.add(task);db.flush()
        record(db,user,'GitHub issue imported',json.dumps({'summary':f"#{number}: {issue['title']}",'project_id':project_id,'github_issue_id':issue['id'],'task_id':task.id,'repository':claims['repository'],'issue_number':number,'source_url':issue['url']}))
        existing.add(issue['id']);created.append(task.id)
    db.commit()
    return {'created_task_ids':created,'skipped_issue_numbers':skipped,'imported_count':len(created)}
