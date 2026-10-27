"""Deterministic, previewed import rules. No AI, external calls, or existing-task rewrites."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, func
from auth import ALGORITHM, ISSUER, SECRET_KEY, Database
from models import AutomationRule, User
from tracker import CurrentUser, project_access, record, valid_assignee

router = APIRouter(prefix='/api/projects', tags=['Import automation'])
ACTIVATION_ISSUER = ISSUER+'/rule-activation'


class RuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    keyword: str = Field(min_length=1, max_length=80)
    match_field: Literal['title','description','both'] = 'title'
    priority: Literal['low','medium','high'] | None = None
    assigned_to: int | None = Field(default=None, gt=0)
    checklist: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('name','keyword', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('checklist')
    @classmethod
    def checklist_lines(cls, values):
        lines = list(dict.fromkeys(value.strip() for value in values))
        if any(not line or len(line)>120 or any(ord(char)<32 for char in line) for line in lines):
            raise ValueError('Use up to 10 nonempty checklist lines, each at most 120 characters.')
        return lines

    @model_validator(mode='after')
    def action_required(self):
        if self.priority is None and self.assigned_to is None and not self.checklist:
            raise ValueError('Choose a priority, assignee or checklist action.')
        return self


class RuleUpdate(RuleInput):
    revision: int = Field(ge=1)


class Sample(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1,max_length=200)
    description: str = Field(default='',max_length=8000)
    priority: Literal['low','medium','high'] = 'medium'


class RulePreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    samples: list[Sample] = Field(min_length=1,max_length=5)


class RuleState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    revision: int = Field(ge=1)
    preview_token: str | None = Field(default=None,max_length=2000)


def public_rule(rule):
    return {key:getattr(rule,key) for key in ('id','name','keyword','match_field','priority','assigned_to','enabled','revision')} | {'checklist':json.loads(rule.checklist)}


def rule_access(db,project_id,rule_id):
    rule = db.get(AutomationRule,rule_id)
    if not rule or rule.project_id != project_id:
        raise HTTPException(404,'Automation rule not found')
    return rule


def rule_set(db,project_id):
    return [public_rule(rule) for rule in db.scalars(select(AutomationRule).where(AutomationRule.project_id==project_id,AutomationRule.enabled.is_(True)).order_by(AutomationRule.id))]


def digest(rules):
    return hashlib.sha256(json.dumps(rules,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def matches(rule,title,description):
    text = title if rule['match_field']=='title' else description if rule['match_field']=='description' else title+'\n'+description
    return rule['keyword'].casefold() in text.casefold()


def effects(db,project_id,rules,title,description):
    for rule in rules:
        if not matches(rule,title,description):continue
        assignee = rule['assigned_to']
        if assignee is not None:
            try:valid_assignee(db,project_id,assignee)
            except HTTPException:
                raise HTTPException(409,f"Rule '{rule['name']}' has an unavailable assignee. Pause or edit the rule, then preview again.") from None
        if len(append_checklist(description,rule['checklist']))>8000:
            raise HTTPException(422,f"Rule '{rule['name']}' would make task details too long. Shorten the source details or checklist.")
        target = db.get(User,assignee) if assignee else None
        return {'rule_id':rule['id'],'rule_name':rule['name'],'revision':rule['revision'],
                'priority':rule['priority'],'assigned_to':assignee,'assignee_name':target.name if target else None,'checklist':rule['checklist']}
    return None


def append_checklist(description,lines):
    return description+('\n\nChecklist:\n'+'\n'.join('- [ ] '+line for line in lines) if lines else '')


def check_snapshot(db,project_id,expected):
    current = rule_set(db,project_id)
    # Older pre-rule previews are valid only when there are no enabled rules.
    if expected != digest(current) and not (expected is None and not current):
        raise HTTPException(409,'Automation rules changed since this preview. Preview the source again before importing.')


def apply(db,user,project_id,task,effect,source):
    if not effect:return
    assignee = effect['assigned_to']
    if assignee is not None:valid_assignee(db,project_id,assignee)
    before = {'priority':task.priority,'assigned_to':task.assigned_to}
    if effect['priority'] is not None:task.priority=effect['priority']
    if assignee is not None:task.assigned_to=assignee
    task.description=append_checklist(task.description or '',effect['checklist'])
    if len(task.description)>8000:
        raise HTTPException(422,'Task details plus automation checklist exceed 8,000 characters. Shorten the source or rule and preview again.')
    db.flush()
    from workflows import notify_assignee
    notify_assignee(db,task,user.id)
    record(db,user,'Automation applied',json.dumps({'summary':f"{effect['rule_name']}: {task.title}",'project_id':project_id,'task_id':task.id,'source':source,'rule_id':effect['rule_id'],'rule_revision':effect['revision'],'before':before,'after':{'priority':task.priority,'assigned_to':task.assigned_to},'checklist':effect['checklist']}))


@router.get('/{project_id}/rules')
def rules(project_id:int,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    return [public_rule(rule) for rule in db.scalars(select(AutomationRule).where(AutomationRule.project_id==project_id).order_by(AutomationRule.id))]


@router.post('/{project_id}/rules',status_code=201)
def create(project_id:int,data:RuleInput,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    if db.scalar(select(func.count()).select_from(AutomationRule).where(AutomationRule.project_id==project_id))>=20:
        raise HTTPException(409,'This project has 20 rules. Edit or reuse an existing rule.')
    if data.assigned_to is not None:valid_assignee(db,project_id,data.assigned_to)
    rule=AutomationRule(project_id=project_id,**data.model_dump(exclude={'checklist'}),checklist=json.dumps(data.checklist),enabled=False)
    db.add(rule);db.flush()
    record(db,user,'Automation rule created',json.dumps({'summary':data.name+' (draft)','project_id':project_id,'rule_id':rule.id}))
    db.commit();return public_rule(rule)


@router.put('/{project_id}/rules/{rule_id}')
def edit(project_id:int,rule_id:int,data:RuleUpdate,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    rule=rule_access(db,project_id,rule_id)
    if rule.revision!=data.revision:raise HTTPException(409,'This rule changed. Reload the rules before editing.')
    if data.assigned_to is not None:valid_assignee(db,project_id,data.assigned_to)
    before=public_rule(rule)
    for key,value in data.model_dump(exclude={'checklist','revision'}).items():setattr(rule,key,value)
    rule.checklist=json.dumps(data.checklist);rule.revision+=1;rule.enabled=False
    record(db,user,'Automation rule edited',json.dumps({'summary':rule.name+' saved as draft','project_id':project_id,'rule_id':rule.id,'before':before,'after':public_rule(rule)}))
    db.commit();return public_rule(rule)


@router.post('/{project_id}/rules/{rule_id}/preview')
def preview(project_id:int,rule_id:int,data:RulePreview,db:Database,user:CurrentUser):
    project_access(db,user,project_id,owner_only=True)
    rule=public_rule(rule_access(db,project_id,rule_id))
    results=[]
    for sample in data.samples:
        effect=effects(db,project_id,[rule],sample.title,sample.description)
        results.append({'matched':bool(effect),'before':sample.model_dump(),'after':{**sample.model_dump(),'description':append_checklist(sample.description,effect['checklist']) if effect else sample.description,'priority':effect['priority'] or sample.priority if effect else sample.priority,'assigned_to':effect['assigned_to'] if effect else None,'assignee_name':effect['assignee_name'] if effect else None}})
    token=None
    if any(result['matched'] for result in results):
        now=datetime.now(timezone.utc)
        token=jwt.encode({'iss':ACTIVATION_ISSUER,'sub':str(user.id),'aud':str(project_id),'rule_id':rule_id,'revision':rule['revision'],'iat':now,'exp':now+timedelta(minutes=5)},SECRET_KEY,algorithm=ALGORITHM)
    return {'results':results,'preview_token':token}


@router.patch('/{project_id}/rules/{rule_id}/state')
def state(project_id:int,rule_id:int,data:RuleState,db:Database,user:CurrentUser):
    project_access(db,user,project_id,write=True,owner_only=True)
    rule=rule_access(db,project_id,rule_id)
    if rule.revision!=data.revision:raise HTTPException(409,'This rule changed. Preview it again.')
    if data.enabled:
        try:
            claims=jwt.decode(data.preview_token or '',SECRET_KEY,algorithms=[ALGORITHM],issuer=ACTIVATION_ISSUER,audience=str(project_id),options={'require':['iss','sub','aud','iat','exp','rule_id','revision']})
            if claims['sub']!=str(user.id) or claims['rule_id']!=rule.id or claims['revision']!=rule.revision:raise ValueError()
        except (jwt.InvalidTokenError,ValueError,TypeError,KeyError):
            raise HTTPException(422,'Preview a matching example before enabling this rule.') from None
        if rule.assigned_to is not None:valid_assignee(db,project_id,rule.assigned_to)
    rule.enabled=data.enabled;rule.revision+=1
    record(db,user,'Automation rule enabled' if data.enabled else 'Automation rule paused',json.dumps({'summary':rule.name,'project_id':project_id,'rule_id':rule.id,'revision':rule.revision}))
    db.commit();return public_rule(rule)
