import json
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
import pytest,httpx
from sqlalchemy import select,func
from test_auth import client,register,login,PASSWORD
from test_tracker import headers
from test_file_imports import setup,preview
from models import EmailGrant,InboxNotice,SlackDelivery,Task
import account_email,workflows


def test_saved_email_import_extracts_text_ignores_attachments_and_deduplicates(client):
    owner,pid,path=setup(client)
    mail=EmailMessage();mail['Subject']='Investigate export failure';mail.set_content('Exports over 10,000 rows fail.');mail.add_attachment(b'ignored',maintype='application',subtype='octet-stream',filename='private.bin')
    response=client.post(path+'/preview',content=mail.as_bytes(),headers={**owner,'Content-Type':'message/rfc822'})
    assert response.status_code==200,response.text
    value=response.json();assert value['source']=='email' and 'private.bin' not in str(value) and 'ignored' not in str(value)
    row=value['rows'][0];assert row['title']=='Investigate export failure' and 'Exports over' in row['description']
    data={'preview_token':value['preview_token'],'row_numbers':[2]}
    assert client.post(path+'/import',json=data,headers=owner).json()['imported_count']==1
    assert client.post(path+'/import',json=data,headers=owner).json()['imported_count']==0


def test_html_email_is_text_without_active_content(client):
    owner,pid,path=setup(client)
    mail=EmailMessage();mail['Subject']='Email task';mail.set_content('<html><head><style>secret-style</style></head><body><p>Read this</p><script>bad()</script><img src="https://external.invalid/pixel"></body></html>',subtype='html')
    value=client.post(path+'/preview',content=mail.as_bytes(),headers={**owner,'Content-Type':'message/rfc822'}).json()
    assert value['rows'][0]['description']=='Read this'


def test_reports_export_and_cursor_pages_are_project_scoped_and_formula_safe(client):
    owner,pid,path=setup(client)
    for title in ['=HYPERLINK("bad")','Second','Third']:
        assert client.post('/api/tasks',json={'project_id':pid,'title':title,'priority':'high'},headers=owner).status_code==201
    report=client.get(f'/api/projects/{pid}/report',headers=owner).json()
    assert report['total_tasks']==3 and report['high_priority_open']==3
    first=client.get(f'/api/projects/{pid}/tasks-page?limit=2',headers=owner).json()
    second=client.get(f"/api/projects/{pid}/tasks-page?limit=2&cursor={first['next_cursor']}",headers=owner).json()
    assert len(first['items'])==2 and len(second['items'])==1 and {r['id'] for r in first['items']}.isdisjoint(r['id'] for r in second['items'])
    export=client.get(f'/api/projects/{pid}/export',headers=owner)
    assert export.status_code==200 and "'=HYPERLINK" in export.text
    register(client,email='outsider@example.com');outsider={'Authorization':'Bearer '+login(client,username='outsider@example.com').json()['access_token']}
    for suffix in ['report','export','tasks-page','integrations']:
        assert client.get(f'/api/projects/{pid}/'+suffix,headers=outsider).status_code==404


def test_in_app_assignment_notices_are_private_and_membership_revocation_hides_them(client):
    owner,pid,path=setup(client);register(client,email='editor@example.com')
    member=client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner).json()
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    task=client.post('/api/tasks',json={'project_id':pid,'title':'Assigned work','assigned_to':member['user_id'],'priority':'high'},headers=owner).json()
    notices=client.get('/api/inbox',headers=editor).json();assert len(notices)==1 and 'High-priority' in notices[0]['message']
    assert client.patch(f"/api/inbox/{notices[0]['id']}/read",headers=owner).status_code==404
    assert client.patch(f"/api/inbox/{notices[0]['id']}/read",headers=editor).status_code==204
    client.patch(f"/api/tasks/{task['id']}",json={'assigned_to':1},headers=owner)
    client.delete(f"/api/projects/{pid}/members/{member['user_id']}",headers=owner)
    assert client.get('/api/inbox',headers=editor).json()==[]


def configure_slack(monkeypatch,pid):
    monkeypatch.setenv('SLACK_WEBHOOK_URL','https://hooks.slack.com/services/fixture/project/credential')
    monkeypatch.setenv('SLACK_PROJECT_ID',str(pid));monkeypatch.setenv('SLACK_CHANNEL_LABEL','Test channel');monkeypatch.setenv('SLACK_SENDING_ENABLED','true')


def test_slack_preview_sends_nothing_and_confirmed_delivery_is_deduplicated(client,monkeypatch):
    owner,pid,path=setup(client);configure_slack(monkeypatch,pid)
    client.post('/api/tasks',json={'project_id':pid,'title':'@here <unsafe>','priority':'high'},headers=owner)
    calls=[]
    class Client:
        def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json):calls.append(json);return httpx.Response(200,text='ok')
    monkeypatch.setattr(workflows.httpx,'Client',Client)
    draft=client.post(f'/api/projects/{pid}/slack/preview',json={'kind':'urgent'},headers=owner).json()
    assert calls==[] and '@here' not in draft['text']
    payload={'preview_token':draft['preview_token'],'confirmed':True}
    assert client.post(f'/api/projects/{pid}/slack/send',json=payload,headers=owner).status_code==200
    assert client.post(f'/api/projects/{pid}/slack/send',json=payload,headers=owner).status_code==409 and len(calls)==1
    assert calls[0]['blocks'][0]['text']['type']=='plain_text' and calls[0]['unfurl_links'] is False
    assert 'credential' not in json.dumps(draft)


def test_slack_disabled_binding_and_uncertain_failures_never_retry(client,monkeypatch):
    owner,pid,path=setup(client);configure_slack(monkeypatch,pid)
    monkeypatch.setenv('SLACK_PROJECT_ID','999');assert client.get(f'/api/projects/{pid}/integrations',headers=owner).json()['slack']['ready'] is False
    monkeypatch.setenv('SLACK_PROJECT_ID',str(pid));draft=client.post(f'/api/projects/{pid}/slack/preview',json={'kind':'summary'},headers=owner).json()
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):calls.append(1);raise httpx.ReadTimeout('private URL must not leak')
    monkeypatch.setattr(workflows.httpx,'Client',Client)
    payload={'preview_token':draft['preview_token'],'confirmed':True}
    response=client.post(f'/api/projects/{pid}/slack/send',json=payload,headers=owner)
    assert response.status_code==502 and 'private URL' not in response.text
    assert client.post(f'/api/projects/{pid}/slack/send',json=payload,headers=owner).status_code==409 and len(calls)==1


def configure_mail(monkeypatch):
    for key,value in {'SMTP_HOST':'smtp.example.test','SMTP_USERNAME':'fixture-user','SMTP_PASSWORD':'fixture-private-password','SMTP_FROM':'sender@example.com','SMTP_PORT':'587'}.items():monkeypatch.setenv(key,value)


def test_email_verification_and_reset_are_single_use_and_revoke_old_sessions(client,monkeypatch):
    configure_mail(monkeypatch);sent=[]
    monkeypatch.setattr(account_email,'send_mail',lambda config,to,kind,token:sent.append((kind,token)))
    register(client);auth={'Authorization':'Bearer '+login(client).json()['access_token']}
    assert client.post('/auth/email-action',json={'email':'person@example.com','kind':'verify'}).status_code==200
    token=sent[-1][1];assert client.post('/auth/verify-email',json={'token':token}).status_code==200
    assert client.get('/auth/account',headers=auth).json()['email_verified'] is True
    assert client.post('/auth/verify-email',json={'token':token}).status_code==422
    client.post('/auth/email-action',json={'email':'person@example.com','kind':'reset'})
    reset=sent[-1][1]
    assert client.post('/auth/reset-password',json={'token':reset,'password':'Password123456789!'}).status_code==422
    new='cobalt lanterns drift beyond seven orchards'
    response=client.post('/auth/reset-password',json={'token':reset,'password':new})
    assert response.status_code==200 and reset not in response.text and new not in response.text
    assert client.get('/me',headers=auth).status_code==401
    assert login(client,password=new).status_code==200 and login(client,password=PASSWORD).status_code==401
    assert client.post('/auth/reset-password',json={'token':reset,'password':new}).status_code==422
    with client.sessions() as db:assert all(row.token_digest!=reset for row in db.scalars(select(EmailGrant)))


def test_logout_revokes_only_that_token(client):
    register(client);first=login(client).json()['access_token'];second=login(client).json()['access_token'];assert first!=second
    assert client.post('/auth/logout',headers={'Authorization':'Bearer '+first}).status_code==204
    assert client.get('/me',headers={'Authorization':'Bearer '+first}).status_code==401
    assert client.get('/me',headers={'Authorization':'Bearer '+second}).status_code==200


def test_unknown_email_response_is_neutral_and_rate_limited(client,monkeypatch):
    configure_mail(monkeypatch);sent=[];monkeypatch.setattr(account_email,'send_mail',lambda *args:sent.append(1))
    for _ in range(3):assert client.post('/auth/email-action',json={'email':'absent@example.com'}).status_code==200
    assert client.post('/auth/email-action',json={'email':'absent@example.com'}).status_code==429 and sent==[]


def test_required_verification_can_be_completed_without_signing_in(client,monkeypatch):
    configure_mail(monkeypatch);monkeypatch.setenv('REQUIRE_VERIFIED_EMAIL','true');sent=[]
    monkeypatch.setattr(account_email,'send_mail',lambda config,to,kind,token:sent.append(token))
    register(client);assert login(client).status_code==403
    assert client.post('/auth/email-action',json={'email':'person@example.com','kind':'verify'}).status_code==200
    assert client.post('/auth/verify-email',json={'token':sent[-1]}).status_code==200
    assert login(client).status_code==200


def test_email_links_expire_and_do_not_allow_the_wrong_action(client,monkeypatch):
    configure_mail(monkeypatch);sent=[];monkeypatch.setattr(account_email,'send_mail',lambda config,to,kind,token:sent.append(token))
    register(client);client.post('/auth/email-action',json={'email':'person@example.com','kind':'verify'})
    token=sent[-1]
    assert client.post('/auth/reset-password',json={'token':token,'password':'cobalt lanterns drift beyond seven orchards'}).status_code==422
    with client.sessions() as db:
        row=db.scalar(select(EmailGrant));row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.post('/auth/verify-email',json={'token':token}).status_code==422


def test_mail_sender_requires_tls_and_uses_fragment_links(monkeypatch):
    configure_mail(monkeypatch);calls=[]
    class Client:
        def __init__(self,host,port,timeout):assert port==587
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def ehlo(self):calls.append('ehlo')
        def starttls(self,context):assert context.check_hostname is True;calls.append('tls')
        def login(self,*args):assert 'tls' in calls
        def send_message(self,message):
            body=message.get_content();assert '/#reset=' in body and '?token=' not in body;calls.append('sent')
    monkeypatch.setattr(account_email.smtplib,'SMTP',Client)
    account_email.send_mail(account_email.settings(),'person@example.com','reset','fixture-token')
    assert calls.count('sent')==1


def test_private_github_credentials_are_scoped_and_never_sent_to_ai(client,monkeypatch):
    import github_imports as github
    owner,pid,path=setup(client)
    monkeypatch.setenv('GITHUB_READ_TOKEN','fixture-private-read-token');monkeypatch.setenv('GITHUB_PROJECT_ID',str(pid));monkeypatch.setenv('GITHUB_ALLOWED_REPOSITORIES','team/private-repo')
    assert github.private_credential('team/private-repo',pid)=='fixture-private-read-token'
    assert github.private_credential('other/repo',pid) is None and github.private_credential('team/private-repo',pid+1) is None
    calls=[]
    def fetch(repo,page,credential):
        calls.append(credential);return [{'id':55,'number':4,'title':'Private issue','body':'Private text','url':'https://github.com/team/private-repo/issues/4'}],False
    monkeypatch.setattr(github,'fetch_issues',fetch)
    result=client.post(f'/api/projects/{pid}/github/preview',json={'repository':'team/private-repo'},headers=owner)
    value=result.json();assert value['restricted_source'] is True and value['ai']['ready'] is False
    assert 'fixture-private-read-token' not in result.text
    assert client.post(f'/api/projects/{pid}/github/analyze',json={'preview_token':value['preview_token'],'issue_numbers':[4],'consent':True},headers=owner).status_code==403


def test_assignment_notification_preference_is_respected(client):
    owner,pid,path=setup(client);register(client,email='editor@example.com')
    member=client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner).json()
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    assert client.patch('/auth/notifications',json={'enabled':False},headers=editor).status_code==200
    client.post('/api/tasks',json={'project_id':pid,'title':'Muted assignment','assigned_to':member['user_id']},headers=owner)
    assert client.get('/api/inbox',headers=editor).json()==[]
    assert client.get('/auth/account',headers=editor).json()['notifications_enabled'] is False
