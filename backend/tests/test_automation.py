import json
from sqlalchemy import select,func
from test_auth import client,register,login
from test_file_imports import setup,preview
from models import ActivityLog,AutomationRule,Task
import github_imports as github
import ai_suggestions

RULE={'name':'Urgent outage','keyword':'outage','match_field':'title','priority':'high','checklist':['Confirm impact','Record resolution']}


def create_rule(client,owner,pid,**changes):
    response=client.post(f'/api/projects/{pid}/rules',json={**RULE,**changes},headers=owner)
    assert response.status_code==201,response.text
    return response.json()


def enable(client,owner,pid,rule,title='Production OUTAGE',description=''):
    path=f"/api/projects/{pid}/rules/{rule['id']}"
    value=client.post(path+'/preview',json={'samples':[{'title':title,'description':description}]},headers=owner)
    assert value.status_code==200,value.text
    token=value.json()['preview_token'];assert token
    result=client.patch(path+'/state',json={'enabled':True,'revision':rule['revision'],'preview_token':token},headers=owner)
    assert result.status_code==200,result.text
    return result.json()


def test_rules_require_preview_and_do_not_rewrite_existing_tasks(client):
    owner,pid,path=setup(client)
    task=client.post('/api/tasks',json={'title':'Existing outage','project_id':pid,'priority':'low'},headers=owner).json()
    rule=create_rule(client,owner,pid)
    assert rule['enabled'] is False
    state=f"/api/projects/{pid}/rules/{rule['id']}/state"
    assert client.patch(state,json={'enabled':True,'revision':1},headers=owner).status_code==422
    nonmatch=client.post(state.replace('/state','/preview'),json={'samples':[{'title':'Routine task'}]},headers=owner).json()
    assert nonmatch['preview_token'] is None
    enabled=enable(client,owner,pid,rule)
    assert enabled['enabled'] and enabled['revision']==2
    existing=client.get('/api/tasks',headers=owner).json()[0]
    assert existing['id']==task['id'] and existing['priority']=='low' and not existing['description']


def test_csv_applies_first_match_assignment_checklist_and_audits_once(client):
    owner,pid,path=setup(client)
    register(client,email='editor@example.com')
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    member=client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner).json()
    rule=enable(client,owner,pid,create_rule(client,owner,pid,assigned_to=member['user_id']))
    enable(client,owner,pid,create_rule(client,owner,pid,name='Later matching rule',priority='low'))
    value=preview(client,path,owner,b'title,description,priority\nService outage,Investigate,low\nDocumentation,Write a guide,low\n').json()
    assert value['rows'][0]['automation']['rule_id']==rule['id'] and value['rows'][1]['automation'] is None
    payload={'preview_token':value['preview_token'],'row_numbers':[2,3]}
    assert client.post(path+'/import',json=payload,headers=owner).json()['imported_count']==2
    team=client.get('/api/tasks?scope=team',headers=owner).json()
    outage=next(task for task in team if task['title']=='Service outage')
    assert outage['priority']=='high' and outage['assigned_to']==member['user_id']
    assert outage['description']=='Investigate\n\nChecklist:\n- [ ] Confirm impact\n- [ ] Record resolution'
    assert client.get('/api/tasks',headers=editor).json()[0]['id']==outage['id']
    assert client.post(path+'/import',json=payload,headers=owner).json()['imported_count']==0
    with client.sessions() as db:assert db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.action=='Automation applied'))==1


def test_changed_or_paused_rules_invalidate_import_preview(client):
    owner,pid,path=setup(client)
    rule=enable(client,owner,pid,create_rule(client,owner,pid))
    value=preview(client,path,owner,b'title\nService outage\n').json()
    result=client.patch(f"/api/projects/{pid}/rules/{rule['id']}/state",json={'enabled':False,'revision':rule['revision']},headers=owner)
    assert result.status_code==200
    payload={'preview_token':value['preview_token'],'row_numbers':[2]}
    assert client.post(path+'/import',json=payload,headers=owner).status_code==409
    assert client.get('/api/tasks',headers=owner).json()==[]


def test_rule_edits_pause_and_stale_revision_activation_is_rejected(client):
    owner,pid,path=setup(client)
    rule=create_rule(client,owner,pid)
    base=f"/api/projects/{pid}/rules/{rule['id']}"
    token=client.post(base+'/preview',json={'samples':[{'title':'outage'}]},headers=owner).json()['preview_token']
    updated=client.put(base,json={**RULE,'priority':'low','revision':1},headers=owner).json()
    assert updated['revision']==2 and updated['enabled'] is False
    assert client.patch(base+'/state',json={'enabled':True,'revision':2,'preview_token':token},headers=owner).status_code==422
    assert client.put(base,json={**RULE,'revision':1},headers=owner).status_code==409


def test_removed_or_demoted_assignee_prevents_stale_import(client):
    owner,pid,path=setup(client)
    register(client,email='editor@example.com')
    member=client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner).json()
    enable(client,owner,pid,create_rule(client,owner,pid,assigned_to=member['user_id']))
    value=preview(client,path,owner,b'title\nService outage\n').json()
    client.put(f"/api/projects/{pid}/members/{member['user_id']}",json={'role':'viewer'},headers=owner)
    assert client.post(path+'/import',json={'preview_token':value['preview_token'],'row_numbers':[2]},headers=owner).status_code==422
    assert preview(client,path,owner,b'title\nService outage\n').status_code==409
    assert client.get('/api/tasks?scope=team',headers=owner).json()==[]


def test_owner_only_management_and_no_cross_project_rule_access(client):
    owner,pid,path=setup(client)
    rule=create_rule(client,owner,pid)
    register(client,email='editor@example.com')
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner)
    base=f'/api/projects/{pid}/rules'
    assert client.get(base,headers=editor).status_code==403
    assert client.post(base,json=RULE,headers=editor).status_code==403
    assert client.post(base+f"/{rule['id']}/preview",json={'samples':[{'title':'outage'}]},headers=editor).status_code==403
    assert client.get(base).status_code==401
    other=client.post('/api/projects',json={'name':'Other'},headers=owner).json()['id']
    assert client.post(f"/api/projects/{other}/rules/{rule['id']}/preview",json={'samples':[{'title':'outage'}]},headers=owner).status_code==404
    assert client.post(base,json={**RULE,'assigned_to':999},headers=owner).status_code==422


def test_github_rules_and_approved_ai_priority_have_explicit_precedence(client,monkeypatch):
    owner,pid,path=setup(client)
    enable(client,owner,pid,create_rule(client,owner,pid,priority='low'))
    issue={'id':91,'number':7,'title':'Service outage','body':'Export fails.','url':'https://github.com/demo/repo/issues/7'}
    monkeypatch.setattr(github,'fetch_issues',lambda *args:([issue],False))
    base=f'/api/projects/{pid}/github'
    value=client.post(base+'/preview',json={'repository':'demo/repo'},headers=owner).json()
    assert value['issues'][0]['automation']['priority']=='low'
    monkeypatch.setattr(ai_suggestions,'generate',lambda *args:{7:{'summary':'Exports fail.','priority':'high','rationale':'Reported failure.','source_quote':'Export fails.','model':'fixture'}})
    draft=client.post(base+'/analyze',json={'preview_token':value['preview_token'],'issue_numbers':[7],'consent':True},headers=owner).json()
    response=client.post(base+'/import',json={'preview_token':draft['preview_token'],'issue_numbers':[7],'accepted_ai_numbers':[7]},headers=owner)
    assert response.status_code==200,response.text
    task=client.get('/api/tasks',headers=owner).json()[0]
    assert task['priority']=='high' and 'Checklist:' in task['description'] and 'Source:' in task['description']


def test_description_matching_and_detail_limit(client):
    owner,pid,path=setup(client)
    rule=create_rule(client,owner,pid,match_field='description')
    enabled=enable(client,owner,pid,rule,title='Routine title',description='OUTAGE in the detail')
    value=preview(client,path,owner,b'title,description\nRoutine,Outage report\n').json()
    assert value['rows'][0]['automation']['rule_id']==enabled['id']
    import csv,io
    text=io.StringIO();writer=csv.writer(text);writer.writerow(['title','description']);writer.writerow(['Task','outage '+('x'*7993)])
    assert preview(client,path,owner,text.getvalue().encode()).status_code==422


def test_empty_project_with_rules_can_still_be_deleted(client):
    owner,pid,path=setup(client);create_rule(client,owner,pid)
    assert client.delete(f'/api/projects/{pid}',headers=owner).status_code==204
    with client.sessions() as db:assert db.scalar(select(func.count()).select_from(AutomationRule))==0


def test_rule_validation_noop_and_unavailable_actions_are_rejected(client):
    owner,pid,path=setup(client);base=f'/api/projects/{pid}/rules'
    for changes in [{'keyword':' '},{'priority':'urgent'},{'priority':None,'checklist':[]},{'checklist':['x'*121]},{'checklist':['line\nbreak']},{'checklist':['']},{'checklist':['step']*11}]:
        assert client.post(base,json={**RULE,**changes},headers=owner).status_code==422
    assert client.get(base,headers=owner).json()==[]


def test_activation_tokens_expire_and_are_bound_to_project_and_rule(client):
    import jwt
    from datetime import datetime,timedelta,timezone
    import automation
    owner,pid,path=setup(client)
    first=create_rule(client,owner,pid);second=create_rule(client,owner,pid,name='Other')
    token=client.post(f"/api/projects/{pid}/rules/{first['id']}/preview",json={'samples':[{'title':'outage'}]},headers=owner).json()['preview_token']
    assert client.patch(f"/api/projects/{pid}/rules/{second['id']}/state",json={'enabled':True,'revision':1,'preview_token':token},headers=owner).status_code==422
    claims=jwt.decode(token,automation.SECRET_KEY,algorithms=[automation.ALGORITHM],audience=str(pid),issuer=automation.ACTIVATION_ISSUER)
    claims['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    expired=jwt.encode(claims,automation.SECRET_KEY,algorithm=automation.ALGORITHM)
    assert client.patch(f"/api/projects/{pid}/rules/{first['id']}/state",json={'enabled':True,'revision':1,'preview_token':expired},headers=owner).status_code==422
