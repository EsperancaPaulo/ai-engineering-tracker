from test_auth import client, register, login


def headers(client):
    register(client)
    return {'Authorization': 'Bearer ' + login(client).json()['access_token']}


def test_website_and_assets(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert 'auth-form' in response.text
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/assets/styles.css').status_code == 200
    assert client.get('/api').json()['message'].endswith('is running')


def test_tracker_requires_login(client):
    for path in ['/api/projects', '/api/tasks', '/api/activity']:
        assert client.get(path).status_code == 401
    assert client.post('/api/projects', json={'name':'No access'}).status_code == 401
    assert client.post('/api/tasks', json={'title':'No access','project_id':1}).status_code == 401
    assert client.patch('/api/tasks/1', json={'status':'done'}).status_code == 401


def test_project_task_activity_flow(client):
    auth = headers(client)
    result = client.post('/api/projects',json={'name':'  AI learning  ','description':'Build a model'}, headers=auth)
    assert result.status_code == 201
    project = result.json()
    assert project['name'] == 'AI learning'
    result = client.post('/api/tasks',json={'title':'Learn embeddings','project_id':project['id'],'priority':'high'},headers=auth)
    assert result.status_code == 201
    task = result.json()
    assert task['status'] == 'todo'
    for status in ['in_progress','done']:
        result = client.patch(f"/api/tasks/{task['id']}",json={'status':status},headers=auth)
        assert result.status_code == 200
        assert result.json()['status'] == status
    assert len(client.get('/api/tasks',headers=auth).json()) == 1
    assert len(client.get('/api/projects',headers=auth).json()) == 1
    assert len(client.get('/api/activity',headers=auth).json()) == 4


def test_user_isolation(client):
    first = headers(client)
    project = client.post('/api/projects',json={'name':'Shared'},headers=first).json()
    task = client.post('/api/tasks',json={'title':'Private task','project_id':project['id']},headers=first).json()
    assert register(client,email='second@example.com').status_code == 201
    second = {'Authorization':'Bearer '+login(client,username='second@example.com').json()['access_token']}
    assert client.get('/api/tasks',headers=second).json() == []
    assert client.get('/api/activity',headers=second).json() == []
    assert client.patch(f"/api/tasks/{task['id']}",json={'status':'done'},headers=second).status_code == 404
    assert client.get('/api/projects',headers=second).json() == []
    assert client.post('/api/tasks',json={'title':'Try assigning','project_id':project['id'],'assigned_to':1},headers=second).status_code == 404


def test_tracker_validation(client):
    auth = headers(client)
    assert client.post('/api/projects',json={'name':'  '},headers=auth).status_code == 422
    assert client.post('/api/tasks',json={'title':'Task','project_id':999},headers=auth).status_code == 404
    assert client.post('/api/tasks',json={'title':'Task','project_id':1,'priority':'urgent'},headers=auth).status_code == 422
    assert client.patch('/api/tasks/999',json={'status':'invalid'},headers=auth).status_code == 422
