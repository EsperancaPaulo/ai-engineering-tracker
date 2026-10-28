import base64,hashlib,importlib.util,json,os,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest,httpx,jwt
from fastapi import HTTPException
from sqlalchemy import select,func
from test_auth import client,register,login
from test_tracker import headers
from models import GmailSource,GmailDraft,Task,ActivityLog,User
import gmail_queue as queue
import gmail_client as gmail

RAW=b'Subject: Review release\nContent-Type: text/plain; charset=utf-8\n\nCheck the release criteria.'


def setup(client,monkeypatch):
    owner=headers(client);pid=client.post('/api/projects',json={'name':'Gmail fixture'},headers=owner).json()['id']
    with client.sessions() as db:db.add(GmailSource(project_id=pid,owner_id=1,account_key='fixture-account',label_id='Label_fixture'));db.commit()
    monkeypatch.setattr(gmail,'read_page',lambda *args:([('a'*64,RAW,'')],None))
    return owner,pid,f'/api/projects/{pid}/gmail'


def ready(client,pid):
    with client.sessions() as db:db.get(GmailSource,pid).next_poll=None;db.commit()


def test_collection_creates_private_drafts_only_and_repeated_message_is_durable(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch)
    assert client.post(path+'/collect',headers=owner).json()['collected_count']==1
    assert client.get('/api/tasks',headers=owner).json()==[]
    draft=client.get(path+'/drafts',headers=owner).json()['items'][0]
    assert draft['title']=='Review release' and 'criteria' in draft['description']
    assert client.post(path+'/collect',headers=owner).status_code==429
    ready(client,pid);assert client.post(path+'/collect',headers=owner).json()['collected_count']==0
    preview=client.post(path+'/preview',json={'draft_ids':[draft['id']]},headers=owner).json()
    assert client.get('/api/tasks',headers=owner).json()==[]
    data={'preview_token':preview['preview_token'],'confirmed':True}
    result=client.post(path+'/import',json=data,headers=owner)
    assert result.json()=={'imported_count':1,'skipped_count':0}
    assert client.post(path+'/import',json=data,headers=owner).status_code==409
    task=client.get('/api/tasks',headers=owner).json()[0]
    assert task['title']=='Review release' and task['priority']=='medium'
    client.delete(f"/api/tasks/{task['id']}",headers=owner)
    ready(client,pid);client.post(path+'/collect',headers=owner)
    assert client.get(path+'/drafts',headers=owner).json()['items']==[]
    with client.sessions() as db:
        receipt=db.scalar(select(GmailDraft));assert receipt.state=='imported' and receipt.description=='' and receipt.title==''


def test_queued_content_only_owner_and_project_scoped(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch);client.post(path+'/collect',headers=owner)
    register(client,email='gmail-editor@example.com');editor={'Authorization':'Bearer '+login(client,username='gmail-editor@example.com').json()['access_token']}
    assert client.get(path,headers=editor).status_code==404
    client.post(f'/api/projects/{pid}/members',headers=owner,json={'email':'gmail-editor@example.com','role':'editor'})
    for endpoint in ('','/drafts'):assert client.get(path+endpoint,headers=editor).status_code==403
    for endpoint in ('collect','preview','import'):
        assert client.post(path+'/'+endpoint,headers=editor,json={'draft_ids':[1],'preview_token':'fixture','confirmed':True}).status_code in (403,422)
    assert client.get(path+'/drafts').status_code==401
    other=client.post('/api/projects',headers=owner,json={'name':'Other'}).json()['id']
    assert client.post(f'/api/projects/{other}/gmail/preview',headers=owner,json={'draft_ids':[1]}).status_code==422


def test_invalid_messages_are_blocked_without_storing_raw_body(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch)
    monkeypatch.setattr(gmail,'read_page',lambda *args:([('b'*64,b'No subject',''),('c'*64,None,'Too large')],None))
    assert client.post(path+'/collect',headers=owner).status_code==200
    drafts=client.get(path+'/drafts',headers=owner).json()['items']
    assert all(d['state']=='blocked' and d['description']=='' and d['problem'] for d in drafts)
    assert client.post(path+'/preview',headers=owner,json={'draft_ids':[drafts[0]['id']]}).status_code==422


def test_dismiss_restore_and_cross_format_duplicate(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch);client.post(path+'/collect',headers=owner)
    draft=client.get(path+'/drafts',headers=owner).json()['items'][0];route=path+f"/drafts/{draft['id']}"
    assert client.patch(route,headers=owner,json={'action':'dismiss'}).json()['state']=='dismissed'
    assert client.get(path+'/drafts',headers=owner).json()['items']==[]
    assert client.get(path+'/drafts?state=dismissed',headers=owner).json()['items'][0]['id']==draft['id']
    assert client.patch(route,headers=owner,json={'action':'restore'}).status_code==200
    client.post('/api/tasks',headers=owner,json={'title':draft['title'],'description':draft['description'],'project_id':pid})
    value=client.post(path+'/preview',headers=owner,json={'draft_ids':[draft['id']]}).json();assert value['rows'][0]['duplicate']
    assert client.post(path+'/import',headers=owner,json={'preview_token':value['preview_token'],'confirmed':True}).json()=={'imported_count':0,'skipped_count':1}


def test_rules_require_fresh_review_before_import(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch);client.post(path+'/collect',headers=owner)
    with client.sessions() as db:
        from models import AutomationRule
        db.add(AutomationRule(project_id=pid,name='Release',keyword='release',match_field='title',priority='high',checklist='["Check evidence"]',enabled=True));db.commit()
    value=client.post(path+'/preview',headers=owner,json={'draft_ids':[1]}).json();assert value['rows'][0]['automation']['priority']=='high'
    with client.sessions() as db:
        rule=db.scalar(select(AutomationRule));rule.revision+=1;db.commit()
    assert client.post(path+'/import',headers=owner,json={'preview_token':value['preview_token'],'confirmed':True}).status_code==409
    fresh=client.post(path+'/preview',headers=owner,json={'draft_ids':[1]}).json()
    assert client.post(path+'/import',headers=owner,json={'preview_token':fresh['preview_token'],'confirmed':True}).status_code==200
    task=client.get('/api/tasks',headers=owner).json()[0];assert task['priority']=='high' and 'Check evidence' in task['description']


def test_expired_tampered_and_wrong_project_reviews_fail(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch);client.post(path+'/collect',headers=owner)
    value=client.post(path+'/preview',headers=owner,json={'draft_ids':[1]}).json()
    claims=jwt.decode(value['preview_token'],queue.SECRET_KEY,algorithms=[queue.ALGORITHM],audience=str(pid),issuer=queue.PREVIEW_ISSUER)
    claims['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    for token in [value['preview_token']+'broken',jwt.encode(claims,queue.SECRET_KEY,algorithm=queue.ALGORITHM)]:
        assert client.post(path+'/import',headers=owner,json={'preview_token':token,'confirmed':True}).status_code==422
    assert client.post(path+'/import',headers=owner,json={'preview_token':value['preview_token'],'confirmed':False}).status_code==422
    other=client.post('/api/projects',headers=owner,json={'name':'Other'}).json()['id']
    assert client.post(f'/api/projects/{other}/gmail/import',headers=owner,json={'preview_token':value['preview_token'],'confirmed':True}).status_code==422


def test_failures_backoff_and_resume_cursor_are_durable(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch)
    def fail(*args):raise HTTPException(503,'Gmail unavailable')
    monkeypatch.setattr(gmail,'read_page',fail)
    assert client.post(path+'/collect',headers=owner).status_code==503
    with client.sessions() as db:assert db.get(GmailSource,pid).failures==1 and db.get(GmailSource,pid).next_poll
    assert client.post(path+'/collect',headers=owner).status_code==429
    ready(client,pid);monkeypatch.setattr(gmail,'read_page',lambda *args:([], 'next-fixture'))
    assert client.post(path+'/collect',headers=owner).json()['more_pages']
    with client.sessions() as db:assert db.get(GmailSource,pid).cursor=='next-fixture' and db.get(GmailSource,pid).failures==0
    assert client.patch(path+'/automatic',headers=owner,json={'enabled':True}).json()['automatic']
    assert client.patch(path+'/automatic',headers=owner,json={'enabled':False}).json()['automatic'] is False


def test_pending_queue_limit_and_pagination(client,monkeypatch):
    owner,pid,path=setup(client,monkeypatch)
    with client.sessions() as db:
        for i in range(100):db.add(GmailDraft(project_id=pid,owner_id=1,message_key=hashlib.sha256(str(i).encode()).hexdigest(),title='Fixture',description='Text'))
        db.commit()
    assert client.post(path+'/collect',headers=owner).status_code==409
    page=client.get(path+'/drafts',headers=owner).json();assert len(page['items'])==25 and page['next_cursor']
    next_page=client.get(path+'/drafts?cursor='+str(page['next_cursor']),headers=owner).json()
    assert not set(r['id'] for r in page['items'])&set(r['id'] for r in next_page['items'])


def test_fixed_gmail_origin_label_filter_and_bounded_raw_messages(monkeypatch):
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.headers['Authorization']=='Bearer fixture-access'
        if request.url.path.endswith('/messages'):
            assert request.url.params['labelIds']=='Label_test' and request.url.params['maxResults']=='5'
            return httpx.Response(200,json={'messages':[{'id':'first'},{'id':'removed'}],'nextPageToken':'page-two'})
        return httpx.Response(200,json={'labelIds':['Label_test'] if request.url.path.endswith('/first') else [],'raw':base64.urlsafe_b64encode(RAW).decode()})
    monkeypatch.setattr(gmail,'token',lambda *args:'fixture-access')
    monkeypatch.setattr(gmail,'http_client',lambda:httpx.Client(transport=httpx.MockTransport(respond)))
    rows,cursor=gmail.read_page(1,1,'account','Label_test',None)
    assert len(rows)==1 and rows[0][1]==RAW and cursor=='page-two'
    assert all(r.url.host=='gmail.googleapis.com' and r.method=='GET' for r in calls)


def test_private_token_refresh_is_bound_and_atomic(tmp_path,monkeypatch):
    monkeypatch.setattr(gmail,'ROOT',tmp_path)
    value={'project_id':1,'owner_id':2,'account_key':'fixture-account','scope':gmail.SCOPE,'client_id':'fixture','client_secret':'fixture','refresh_token':'fixture-refresh','access_token':'old','expires_at':0}
    gmail.write_private(gmail.credential_path(1),value)
    requests=[]
    def respond(request):
        requests.append(request);assert request.url.host=='oauth2.googleapis.com'
        return httpx.Response(200,json={'access_token':'new-access','expires_in':3600,'scope':gmail.SCOPE})
    monkeypatch.setattr(gmail,'http_client',lambda:httpx.Client(transport=httpx.MockTransport(respond)))
    assert gmail.token(1,2,'fixture-account')=='new-access' and len(requests)==1
    assert gmail.token(1,2,'fixture-account')=='new-access' and len(requests)==1
    assert gmail.credential_path(1).stat().st_mode&0o777==0o600
    assert gmail.folder().stat().st_mode&0o777==0o700
    with pytest.raises(HTTPException):gmail.token(1,3,'fixture-account')
    gmail.credential_path(1).chmod(0o644)
    with pytest.raises(HTTPException):gmail.token(1,2,'fixture-account')


def test_provider_failure_does_not_echo_tokens_or_private_bodies():
    transport=httpx.MockTransport(lambda request:httpx.Response(403,text='fixture-private-provider-body'))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HTTPException) as error:gmail.bounded(client,'GET',gmail.API+'/messages')
    assert 'fixture-private' not in str(error.value.detail)


def test_gmail_migration_preserves_existing_records_and_is_idempotent(client):
    from migrate_gmail import upgrade
    owner=headers(client)
    with client.sessions() as db:
        before=db.scalar(select(User.password_hash));connection=db.connection()
        assert upgrade(connection) is True and upgrade(connection) is False
        assert db.scalar(select(User.password_hash))==before
        assert db.scalar(select(func.count()).select_from(GmailDraft))==0
        assert db.scalar(select(func.count()).select_from(GmailSource))==0
        db.commit()


def test_local_oauth_uses_pkce_state_readonly_scope_and_no_message_collection(tmp_path,monkeypatch):
    import io
    from urllib.parse import urlsplit,parse_qs,urlencode,parse_qsl
    spec=importlib.util.spec_from_file_location('connect_gmail_test',Path(__file__).resolve().parents[2]/'scripts/connect_gmail.py')
    connector=importlib.util.module_from_spec(spec);spec.loader.exec_module(connector)
    opened={};callbacks=[];calls=[]
    class Server:
        server_port=45678
        def __init__(self,address,handler):assert address==('127.0.0.1',0);self.handler=handler
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def handle_request(self):
            handler=self.handler.__new__(self.handler);handler.wfile=io.BytesIO();handler.send_response=lambda code:callbacks.append(code);handler.send_header=lambda *args:None;handler.end_headers=lambda:None
            state=opened['params']['state'][0] if callbacks else 'wrong-state'
            handler.path='/oauth/callback?'+urlencode({'state':state,'code':'fixture-code'});handler.do_GET()
    monkeypatch.setattr(connector,'HTTPServer',Server)
    def opener(url):opened.update(params=parse_qs(urlsplit(url).query));return True
    def respond(request):
        calls.append(request)
        if request.url.host=='oauth2.googleapis.com':
            data=dict(parse_qsl(request.content.decode()));challenge=base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'].encode()).digest()).decode().rstrip('=')
            assert opened['params']['code_challenge']==[challenge] and data['code']=='fixture-code'
            return httpx.Response(200,json={'scope':gmail.SCOPE,'access_token':'fixture','refresh_token':'fixture','expires_in':3600})
        if request.url.path.endswith('/profile'):return httpx.Response(200,json={'emailAddress':'fixture@example.com'})
        return httpx.Response(200,json={'labels':[{'name':'Tracker Inbox','id':'Label_test'}]})
    monkeypatch.setattr(gmail,'http_client',lambda:httpx.Client(transport=httpx.MockTransport(respond)))
    value,label=connector.authorize({'client_id':'fixture','client_secret':'fixture'},opener)
    assert callbacks==[400,200] and label=='Label_test' and value['scope']==gmail.SCOPE
    assert opened['params']['scope']==[gmail.SCOPE] and opened['params']['code_challenge_method']==['S256']
    assert not any('/messages' in request.url.path for request in calls)


def test_desktop_json_requires_google_endpoints_and_worker_respects_pause(client,monkeypatch,tmp_path):
    spec=importlib.util.spec_from_file_location('connect_gmail_test',Path(__file__).resolve().parents[2]/'scripts/connect_gmail.py')
    connector=importlib.util.module_from_spec(spec);spec.loader.exec_module(connector)
    path=tmp_path/'client.json';path.write_text(json.dumps({'installed':{'auth_uri':'https://invalid.example/auth','token_uri':gmail.TOKEN,'client_id':'fixture.apps.googleusercontent.com','client_secret':'fixture'}}))
    with pytest.raises(RuntimeError):connector.client_settings(path)
    owner,pid,route=setup(client,monkeypatch)
    with client.sessions() as db:
        with pytest.raises(HTTPException) as error:queue.collect(db,db.get(User,1),pid,automatic_only=True)
    assert error.value.status_code==409
