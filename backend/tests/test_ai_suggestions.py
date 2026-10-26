import json
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_auth import client, register, login
from test_github_imports import setup
from models import ActivityLog
import ai_suggestions as ai
import github_imports as github

SUGGESTION={'summary':'Review untrusted issue text.','priority':'high','rationale':'The issue needs owner assessment; impact is unclear.','source_quote':'untrusted text','model':'fixture-model'}


def preview(client,monkeypatch):
    auth,pid,_=setup(client,monkeypatch)
    path=f'/api/projects/{pid}/github'
    value=client.post(path+'/preview',json={'repository':'demo/repo'},headers=auth).json()
    return auth,pid,path,{'preview_token':value['preview_token'],'issue_numbers':[3]}


def test_ai_draft_never_saves_tasks_and_only_approved_draft_is_applied(client,monkeypatch):
    auth,pid,path,payload=preview(client,monkeypatch)
    calls=[]
    def generate(issues,user_id):
        calls.append(issues);return {3:SUGGESTION}
    monkeypatch.setattr(ai,'generate',generate)
    assert client.post(path+'/analyze',json=payload,headers=auth).status_code==422
    result=client.post(path+'/analyze',json={**payload,'consent':True},headers=auth)
    assert result.status_code==200 and len(calls)==1
    assert client.get('/api/tasks',headers=auth).json()==[]
    reviewed=result.json()
    imported=client.post(path+'/import',json={**payload,'preview_token':reviewed['preview_token'],'accepted_ai_numbers':[3]},headers=auth)
    assert imported.status_code==200
    task=client.get('/api/tasks',headers=auth).json()[0]
    assert task['priority']=='high' and 'AI summary (reviewed):' in task['description']
    assert '<script>untrusted text</script>' in task['description'] and 'https://github.com/demo/repo/issues/3' in task['description']
    with client.sessions() as db:
        audit=json.loads(db.scalar(select(ActivityLog.details).where(ActivityLog.action=='AI suggestion reviewed')))
        assert audit['approved'] is True and audit['suggestion']==SUGGESTION
    # The same approved preview is safe to retry without creating another task or review.
    assert client.post(path+'/import',json={**payload,'preview_token':reviewed['preview_token'],'accepted_ai_numbers':[3]},headers=auth).json()['imported_count']==0


def test_generated_suggestions_are_not_applied_without_explicit_selection(client,monkeypatch):
    auth,pid,path,payload=preview(client,monkeypatch)
    monkeypatch.setattr(ai,'generate',lambda *args:{3:SUGGESTION})
    token=client.post(path+'/analyze',json={**payload,'consent':True},headers=auth).json()['preview_token']
    assert client.post(path+'/import',json={**payload,'preview_token':token},headers=auth).status_code==200
    task=client.get('/api/tasks',headers=auth).json()[0]
    assert task['priority']=='medium' and 'AI summary' not in task['description']
    with client.sessions() as db:
        assert json.loads(db.scalar(select(ActivityLog.details).where(ActivityLog.action=='AI suggestion reviewed')))['approved'] is False


def test_ai_approvals_must_exist_in_signed_preview_and_selected_import(client,monkeypatch):
    auth,pid,path,payload=preview(client,monkeypatch)
    assert client.post(path+'/import',json={**payload,'accepted_ai_numbers':[3]},headers=auth).status_code==422
    assert client.post(path+'/import',json={**payload,'accepted_ai_numbers':[99]},headers=auth).status_code==422
    assert client.post(path+'/analyze',json={**payload,'consent':False},headers=auth).status_code==422
    assert client.post(path+'/analyze',json={**payload,'issue_numbers':[99],'consent':True},headers=auth).status_code==422


def test_ai_owner_project_and_preview_authorization_before_provider_call(client,monkeypatch):
    auth,pid,path,payload=preview(client,monkeypatch)
    provider=[];monkeypatch.setattr(ai,'generate',lambda *args:provider.append(args))
    register(client,email='editor@example.com')
    editor={'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=auth)
    assert client.post(path+'/analyze',json={**payload,'consent':True},headers=editor).status_code==403
    assert client.get(path+'/ai-config',headers=editor).status_code==403
    assert client.post(path+'/analyze',json={**payload,'consent':True}).status_code==401
    other=client.post('/api/projects',json={'name':'Other'},headers=auth).json()['id']
    assert client.post(f'/api/projects/{other}/github/analyze',json={**payload,'consent':True},headers=auth).status_code==422
    assert client.post(path+'/analyze',json={**payload,'preview_token':payload['preview_token'][:-6]+'broken','consent':True},headers=auth).status_code==422
    assert not provider


def configure(monkeypatch):
    monkeypatch.setenv('AI_SUGGESTIONS_ENABLED','true');monkeypatch.setenv('OPENAI_API_KEY','fixture-provider-credential')
    monkeypatch.setenv('OPENAI_MODEL','fixture-model');monkeypatch.setattr(ai,'_requests',{})


def service(monkeypatch,body,status=200):
    requests=[]
    class Client:
        def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):
            assert url=='https://api.openai.com/v1/responses'
            requests.append(json)
            assert json['store'] is False and json['max_output_tokens']==1800 and 'tools' not in json
            assert 'fixture-provider-credential' not in str(json)
            return httpx.Response(status,json=body,request=httpx.Request('POST',url))
    monkeypatch.setattr(ai.httpx,'Client',Client)
    return requests


def response(suggestions=None,**changes):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'suggestions':suggestions or [{'number':3,**{k:v for k,v in SUGGESTION.items() if k!='model'}}]})}]}],**changes}


def test_provider_request_has_only_source_data_and_structured_output(monkeypatch):
    configure(monkeypatch);requests=service(monkeypatch,response())
    issues=[{'number':3,'title':'Issue','body':'untrusted text','secret_internal_note':'must not be sent'}]
    assert ai.generate(issues,1)=={3:SUGGESTION}
    assert json.loads(requests[0]['input'])=={'issues':[{'number':3,'title':'Issue','body':'untrusted text'}]}
    assert requests[0]['text']['format']['strict'] is True
    with pytest.raises(HTTPException) as error:ai.generate(issues,1)
    assert error.value.status_code==429 and len(requests)==1


@pytest.mark.parametrize('changes',[{'source_quote':'invented evidence'},{'priority':'urgent'},{'number':99},{'summary':' '},{'rationale':'x'*401}])
def test_invalid_or_ungrounded_ai_output_is_rejected(monkeypatch,changes):
    configure(monkeypatch);service(monkeypatch,response([{'number':3,**{k:v for k,v in SUGGESTION.items() if k!='model'},**changes}]))
    with pytest.raises(HTTPException) as error:ai.generate([{'number':3,'title':'Issue','body':'untrusted text'}],1)
    assert error.value.status_code==502 and 'fixture-provider-credential' not in str(error.value.detail)


@pytest.mark.parametrize('status,expected',[(401,503),(403,503),(429,429),(500,502)])
def test_provider_failures_are_safe_and_not_automatically_retried(monkeypatch,status,expected):
    configure(monkeypatch);calls=service(monkeypatch,{'error':{'message':'sensitive upstream contents'}},status)
    with pytest.raises(HTTPException) as error:ai.generate([{'number':3,'title':'Issue','body':'untrusted text'}],1)
    assert error.value.status_code==expected and len(calls)==1 and 'sensitive' not in str(error.value.detail)


def test_missing_key_is_honest_and_original_import_still_works(client,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    auth,pid,path,payload=preview(client,monkeypatch)
    assert client.get(path+'/ai-config',headers=auth).json()['ready'] is False
    assert client.post(path+'/analyze',json={**payload,'consent':True},headers=auth).status_code==503
    assert client.post(path+'/import',json=payload,headers=auth).json()['imported_count']==1

def test_expired_preview_never_reaches_provider(client,monkeypatch):
    import jwt
    from datetime import datetime,timedelta,timezone
    auth,pid,path,payload=preview(client,monkeypatch)
    claims=jwt.decode(payload['preview_token'],github.SECRET_KEY,algorithms=[github.ALGORITHM],audience=str(pid),issuer=github.PREVIEW_ISSUER)
    claims['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    token=jwt.encode(claims,github.SECRET_KEY,algorithm=github.ALGORITHM)
    called=[];monkeypatch.setattr(ai,'generate',lambda *args:called.append(args))
    assert client.post(path+'/analyze',json={**payload,'preview_token':token,'consent':True},headers=auth).status_code==422
    assert not called


@pytest.mark.parametrize('body',[{'status':'incomplete','output':[]},{'status':'completed','output':[{'type':'message','content':[{'type':'refusal','refusal':'No'}]}]},response([{'number':3,**{k:v for k,v in SUGGESTION.items() if k!='model'}},{'number':3,**{k:v for k,v in SUGGESTION.items() if k!='model'}}])])
def test_incomplete_refused_or_duplicate_output_is_not_used(monkeypatch,body):
    configure(monkeypatch);service(monkeypatch,body)
    with pytest.raises(HTTPException):ai.generate([{'number':3,'title':'Issue','body':'untrusted text'}],1)


def test_provider_timeout_is_safe_and_not_retried(monkeypatch):
    configure(monkeypatch);calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):calls.append(1);raise httpx.ReadTimeout('private upstream detail')
    monkeypatch.setattr(ai.httpx,'Client',Client)
    with pytest.raises(HTTPException) as error:ai.generate([{'number':3,'title':'Issue','body':'untrusted text'}],1)
    assert len(calls)==1 and 'private upstream' not in str(error.value.detail)
