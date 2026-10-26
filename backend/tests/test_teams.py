import json
import pytest
from sqlalchemy import select
from test_auth import client, register, login
from test_tracker import headers
from models import ProjectMember, Task


def account(client,email,name):
    result=register(client,email=email,name=name)
    assert result.status_code==201
    return result.json()['id'], {'Authorization':'Bearer '+login(client,username=email).json()['access_token']}


def team(client):
    owner=headers(client)
    project=client.post('/api/projects',json={'name':'Protected project'},headers=owner).json()
    editor_id,editor=account(client,'editor@example.com','Editor')
    viewer_id,viewer=account(client,'viewer@example.com','Viewer')
    outsider_id,outsider=account(client,'outsider@example.com','Outsider')
    for email,role in [('editor@example.com','editor'),('viewer@example.com','viewer')]:
        assert client.post(f"/api/projects/{project['id']}/members",json={'email':email,'role':role},headers=owner).status_code==201
    return project,owner,(editor_id,editor),(viewer_id,viewer),(outsider_id,outsider)


def test_project_private_until_added(client):
    p,owner,(eid,editor),(vid,viewer),(_,outside)=team(client)
    assert client.get('/api/projects',headers=owner).json()[0]['role']=='owner'
    assert client.get('/api/projects',headers=editor).json()[0]['role']=='editor'
    assert client.get('/api/projects',headers=viewer).json()[0]['role']=='viewer'
    assert client.get('/api/projects',headers=outside).json()==[]
    assert client.get(f"/api/projects/{p['id']}/members",headers=outside).status_code==404
    members=client.get(f"/api/projects/{p['id']}/members",headers=viewer).json()
    assert len(members)==3 and all('email' not in member for member in members)


def test_owner_editor_viewer_write_permissions(client):
    p,owner,(eid,editor),(vid,viewer),(_,outside)=team(client)
    path=f"/api/projects/{p['id']}"
    assert client.put(path,json={'name':'Editor rename'},headers=editor).status_code==200
    assert client.put(path,json={'name':'Viewer rename'},headers=viewer).status_code==403
    assert client.put(path,json={'name':'Outsider rename'},headers=outside).status_code==404
    assert client.delete(path,headers=editor).status_code==403
    assert client.delete(path,headers=viewer).status_code==403
    assert client.post('/api/tasks',json={'title':'No write','project_id':p['id']},headers=viewer).status_code==403
    assert client.post('/api/tasks',json={'title':'No access','project_id':p['id']},headers=outside).status_code==404


def test_assignment_and_team_view(client):
    p,owner,(eid,editor),(vid,viewer),(oid,outside)=team(client)
    task=client.post('/api/tasks',json={'title':'Delegated','project_id':p['id'],'assigned_to':eid,'description':'Success criteria'},headers=owner)
    assert task.status_code==201
    assert task.json()['assignee_name']=='Editor'
    task_id=task.json()['id']
    assert client.get('/api/tasks',headers=owner).json()==[]
    assert client.get('/api/tasks',headers=editor).json()[0]['can_edit'] is True
    assert client.get('/api/tasks?scope=team',headers=viewer).json()[0]['can_edit'] is False
    assert client.get('/api/tasks?scope=team',headers=outside).json()==[]
    assert client.get('/api/tasks?scope=invalid',headers=owner).status_code==422
    assert client.patch(f'/api/tasks/{task_id}',json={'status':'done'},headers=viewer).status_code==403
    assert client.delete(f'/api/tasks/{task_id}',headers=outside).status_code==404
    assert client.patch(f'/api/tasks/{task_id}',json={'status':'done'},headers=editor).status_code==200
    assert client.patch(f'/api/tasks/{task_id}',json={'assigned_to':1},headers=editor).status_code==403
    assert client.patch(f'/api/tasks/{task_id}',json={'assigned_to':vid},headers=owner).status_code==422
    assert client.patch(f'/api/tasks/{task_id}',json={'assigned_to':oid},headers=owner).status_code==422
    assert client.post('/api/tasks',json={'title':'Escalate','project_id':p['id'],'assigned_to':1},headers=editor).status_code==403
    assert client.patch(f'/api/tasks/{task_id}',json={'assigned_to':1},headers=owner).status_code==200
    assert client.delete(f'/api/tasks/{task_id}',headers=owner).status_code==204


def test_editor_cannot_change_others_tasks(client):
    p,owner,(eid,editor),_,_=team(client)
    task=client.post('/api/tasks',json={'title':'Owner task','project_id':p['id']},headers=owner).json()
    assert client.get('/api/tasks?scope=team',headers=editor).json()[0]['can_edit'] is False
    assert client.patch(f"/api/tasks/{task['id']}",json={'title':'Hijack'},headers=editor).status_code==403
    assert client.delete(f"/api/tasks/{task['id']}",headers=editor).status_code==403


def test_member_roles_revocation_and_owner_protection(client):
    p,owner,(eid,editor),(vid,viewer),(_,outside)=team(client)
    path=f"/api/projects/{p['id']}/members"
    assert client.post(path,json={'email':'outsider@example.com','role':'editor'},headers=editor).status_code==403
    assert client.put(path+f'/{vid}',json={'role':'editor'},headers=viewer).status_code==403
    assert client.post(path,json={'email':'outsider@example.com','role':'owner'},headers=owner).status_code==422
    assert client.put(path+'/1',json={'role':'viewer'},headers=owner).status_code==409
    assert client.delete(path+'/1',headers=owner).status_code==409
    assert client.put(path+f'/{eid}',json={'role':'viewer'},headers=owner).status_code==200
    assert client.post('/api/tasks',json={'title':'Demoted','project_id':p['id']},headers=editor).status_code==403
    assert client.delete(path+f'/{eid}',headers=owner).status_code==204
    assert client.get('/api/projects',headers=editor).json()==[]
    assert client.get(path,headers=editor).status_code==404
    assert client.post(path,json={'email':'missing@example.com'},headers=owner).status_code==404
    assert client.post(path,json={'email':'viewer@example.com'},headers=owner).status_code==409


def test_reassign_before_removing_member(client):
    p,owner,(eid,editor),_,_=team(client)
    task=client.post('/api/tasks',json={'title':'Keep task','project_id':p['id'],'assigned_to':eid},headers=owner).json()
    path=f"/api/projects/{p['id']}/members/{eid}"
    assert client.delete(path,headers=owner).status_code==409
    assert client.patch(f"/api/tasks/{task['id']}",json={'assigned_to':1},headers=owner).status_code==200
    assert client.delete(path,headers=owner).status_code==204
    assert client.get('/api/tasks?scope=team',headers=editor).json()==[]
    assert client.get('/api/tasks',headers=owner).json()[0]['title']=='Keep task'


def test_move_requires_destination_access_and_assignee_membership(client):
    p,owner,(eid,editor),_,(_,outside)=team(client)
    private=client.post('/api/projects',json={'name':'Other private'},headers=outside).json()
    task=client.post('/api/tasks',json={'title':'No leaks','project_id':p['id'],'assigned_to':eid},headers=owner).json()
    assert client.patch(f"/api/tasks/{task['id']}",json={'project_id':private['id']},headers=editor).status_code==404
    own=client.post('/api/projects',json={'name':'Destination'},headers=owner).json()
    assert client.patch(f"/api/tasks/{task['id']}",json={'project_id':own['id']},headers=owner).status_code==422
    assert client.patch(f"/api/tasks/{task['id']}",json={'project_id':own['id'],'assigned_to':1},headers=owner).status_code==200


def test_project_delete_cleans_memberships(client):
    p,owner,_,_,_=team(client)
    assert client.delete(f"/api/projects/{p['id']}",headers=owner).status_code==204
    with client.sessions() as db:
        assert list(db.scalars(select(ProjectMember)))==[]


def test_membership_endpoints_require_auth(client):
    assert client.get('/api/projects/1/members').status_code==401
    assert client.post('/api/projects/1/members',json={'email':'editor@example.com'}).status_code==401
    assert client.put('/api/projects/1/members/2',json={'role':'viewer'}).status_code==401
    assert client.delete('/api/projects/1/members/2').status_code==401
