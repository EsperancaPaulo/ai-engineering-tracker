import pytest,jwt,httpx
from test_auth import client,register,login
from test_tracker import headers
from models import ActivityLog
import github_imports as github
from sqlalchemy import select

ISSUES=[{'id':9001,'number':3,'title':'Issue to review','body':'<script>untrusted text</script>','url':'https://github.com/demo/repo/issues/3'}]

def setup(client,monkeypatch):
    auth=headers(client)
    project=client.post('/api/projects',json={'name':'Importer'},headers=auth).json()
    calls=[]
    def fake(repo,page):calls.append((repo,page));return ISSUES,True
    monkeypatch.setattr(github,'fetch_issues',fake)
    return auth,project['id'],calls

def test_preview_does_not_save_and_selected_import_is_idempotent(client,monkeypatch):
    auth,pid,calls=setup(client,monkeypatch)
    response=client.post(f'/api/projects/{pid}/github/preview',json={'repository':'demo/repo'},headers=auth)
    assert response.status_code==200 and calls==[('demo/repo',1)]
    preview=response.json()
    assert preview['has_next'] is True
    assert client.get('/api/tasks',headers=auth).json()==[]
    payload={'preview_token':preview['preview_token'],'issue_numbers':[3]}
    response=client.post(f'/api/projects/{pid}/github/import',json=payload,headers=auth)
    assert response.status_code==200 and response.json()['imported_count']==1
    task=client.get('/api/tasks',headers=auth).json()[0]
    assert task['title']=='Issue to review' and task['priority']=='medium' and task['status']=='todo'
    assert 'Source: https://github.com/demo/repo/issues/3' in task['description']
    retry=client.post(f'/api/projects/{pid}/github/import',json=payload,headers=auth).json()
    assert retry['imported_count']==0 and retry['skipped_issue_numbers']==[3]
    assert len(client.get('/api/tasks',headers=auth).json())==1
    assert client.post(f'/api/projects/{pid}/github/preview',json={'repository':'demo/repo'},headers=auth).json()['issues'][0]['already_imported'] is True

@pytest.mark.parametrize('repo',['https://github.com/demo/repo','../repo','demo/..','demo/repo?token=secret','demo/repo/../../internal','demo@evil/repo'])
def test_rejects_arbitrary_urls_and_paths(client,monkeypatch,repo):
    auth,pid,calls=setup(client,monkeypatch)
    assert client.post(f'/api/projects/{pid}/github/preview',json={'repository':repo},headers=auth).status_code==422
    assert calls==[]

def test_owner_only_and_preview_bound_to_owner_project_selection(client,monkeypatch):
    auth,pid,_=setup(client,monkeypatch)
    register(client,email='editor@example.com')
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=auth)
    path=f'/api/projects/{pid}/github'
    assert client.post(path+'/preview',json={'repository':'demo/repo'},headers=editor).status_code==403
    assert client.post(path+'/preview',json={'repository':'demo/repo'}).status_code==401
    preview=client.post(path+'/preview',json={'repository':'demo/repo'},headers=auth).json()
    payload={'preview_token':preview['preview_token'],'issue_numbers':[3]}
    assert client.post(path+'/import',json=payload,headers=editor).status_code==403
    assert client.post(path+'/import',json={**payload,'issue_numbers':[99]},headers=auth).status_code==422
    other=client.post('/api/projects',json={'name':'Other'},headers=auth).json()
    assert client.post(f"/api/projects/{other['id']}/github/import",json=payload,headers=auth).status_code==422
    token=preview['preview_token'];tampered=token[:-5]+'abcde'
    assert client.post(path+'/import',json={**payload,'preview_token':tampered},headers=auth).status_code==422

def test_github_client_excludes_prs_retries_and_sends_no_credentials(monkeypatch):
    count=[]
    class Client:
        def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,params,headers):
            assert url=='https://api.github.com/repos/demo/repo/issues'
            assert 'Authorization' not in headers and params['page']==2
            count.append(url)
            if len(count)==1:return httpx.Response(503)
            return httpx.Response(200,json=[{'id':1,'number':2,'title':'PR','pull_request':{}},{'id':2,'number':3,'title':'Issue','body':'Details'}])
    monkeypatch.setattr(github.httpx,'Client',Client)
    issues,next_page=github.fetch_issues('demo/repo',2)
    assert len(count)==2 and len(issues)==1 and issues[0]['title']=='Issue' and next_page is False
