import json
import pytest
from test_auth import client, register, login
from test_tracker import headers


def setup_items(client):
    auth = headers(client)
    project = client.post('/api/projects',json={'name':'Original project','description':'Original description'},headers=auth).json()
    task = client.post('/api/tasks',json={'title':'Original task','project_id':project['id']},headers=auth).json()
    return auth,project,task


def test_edit_project_and_task_persist_with_audit(client):
    auth,project,task = setup_items(client)
    result = client.put(f"/api/projects/{project['id']}",json={'name':' Updated project ','description':'New description'},headers=auth)
    assert result.status_code == 200
    assert result.json()['name'] == 'Updated project'
    assert client.get('/api/projects',headers=auth).json()[0]['description'] == 'New description'
    second = client.post('/api/projects',json={'name':'Second project'},headers=auth).json()
    result = client.patch(f"/api/tasks/{task['id']}",json={'title':' Revised task ','priority':'high','status':'in_progress','project_id':second['id']},headers=auth)
    assert result.status_code == 200
    updated = client.get('/api/tasks',headers=auth).json()[0]
    assert updated['title'] == 'Revised task' and updated['priority'] == 'high'
    assert updated['status'] == 'in_progress' and updated['project_id'] == second['id']
    logs = client.get('/api/activity',headers=auth).json()
    details = json.loads(logs[0]['details'])
    assert details['before']['title'] == 'Original task'
    assert details['after']['title'] == 'Revised task'
    assert details['task_id'] == task['id']
    project_log = next(log for log in logs if log['action'] == 'Project edited')
    assert json.loads(project_log['details'])['before']['description'] == 'Original description'


def test_deletion_blocks_nonempty_and_keeps_audit(client):
    auth,project,task = setup_items(client)
    url = f"/api/projects/{project['id']}"
    assert client.delete(url,headers=auth).status_code == 409
    assert len(client.get('/api/tasks',headers=auth).json()) == 1
    result = client.delete(f"/api/tasks/{task['id']}",headers=auth)
    assert result.status_code == 204 and result.content == b''
    assert client.get('/api/tasks',headers=auth).json() == []
    assert client.delete(url,headers=auth).status_code == 204
    assert client.get('/api/projects',headers=auth).json() == []
    assert client.delete(url,headers=auth).status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}",headers=auth).status_code == 404
    logs = client.get('/api/activity',headers=auth).json()
    deleted = next(log for log in logs if log['action'] == 'Task deleted')
    assert json.loads(deleted['details'])['before']['title'] == 'Original task'
    assert any(log['action'] == 'Project deleted' for log in logs)


def test_cannot_change_or_delete_another_users_task(client):
    first,project,task = setup_items(client)
    register(client,email='other@example.com')
    other={'Authorization':'Bearer '+login(client,username='other@example.com').json()['access_token']}
    path=f"/api/tasks/{task['id']}"
    assert client.patch(path,json={'title':'Stolen'},headers=other).status_code == 404
    assert client.delete(path,headers=other).status_code == 404
    # Nonmembers cannot see or delete this project.
    assert client.get('/api/tasks',headers=other).json() == []
    assert client.delete(f"/api/projects/{project['id']}",headers=other).status_code == 404
    assert client.get('/api/tasks',headers=first).json()[0]['title'] == 'Original task'
    assert client.get('/api/activity',headers=other).json() == []


@pytest.mark.parametrize('method,path,data', [
    ('put','/api/projects/1',{'name':'Edit'}),
    ('patch','/api/tasks/1',{'title':'Edit'}),
    ('delete','/api/projects/1',None),
    ('delete','/api/tasks/1',None),
])
def test_management_requires_auth(client,method,path,data):
    kwargs={'json':data} if data is not None else {}
    assert getattr(client,method)(path,**kwargs).status_code == 401


@pytest.mark.parametrize('data', [{},{'title':' '},{'title':'a'*201},{'priority':'urgent'}, {'project_id':0},{'title':None},{'project_id':None},{'priority':None},{'status':None},{'assigned_to':99}])
def test_task_update_validation(client,data):
    auth,_,task=setup_items(client)
    result=client.patch(f"/api/tasks/{task['id']}",json=data,headers=auth)
    assert result.status_code == 422
    assert client.get('/api/tasks',headers=auth).json()[0]['title'] == 'Original task'


def test_missing_targets_and_project_validation(client):
    auth,project,task=setup_items(client)
    assert client.patch(f"/api/tasks/{task['id']}",json={'project_id':9999},headers=auth).status_code == 404
    assert client.patch('/api/tasks/9999',json={'title':'Missing'},headers=auth).status_code == 404
    assert client.put('/api/projects/9999',json={'name':'Missing'},headers=auth).status_code == 404
    for data in [{'name':' '},{'name':'a'*151},{'name':'Valid','description':'x'*4001},{'name':'Valid','role':'admin'}]:
        assert client.put(f"/api/projects/{project['id']}",json=data,headers=auth).status_code == 422


def test_task_edit_without_status_preserves_status(client):
    auth,_,task=setup_items(client)
    path=f"/api/tasks/{task['id']}"
    client.patch(path,json={'status':'done'},headers=auth)
    result=client.patch(path,json={'title':'Edited only'},headers=auth)
    assert result.status_code == 200 and result.json()['status'] == 'done'
