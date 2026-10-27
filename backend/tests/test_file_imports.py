import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select

from test_auth import client, register, login
from test_tracker import headers
from models import ActivityLog, Task
import file_imports as files

CSV = b'title,description,priority\nReview release,Check the criteria,high\nPrepare update,Collect blockers,\n'


def setup(client):
    owner = headers(client)
    project = client.post('/api/projects', json={'name': 'CSV import project'}, headers=owner).json()
    return owner, project['id'], f"/api/projects/{project['id']}/files"


def preview(client, path, owner, content=CSV):
    return client.post(path+'/preview', content=content, headers={**owner, 'Content-Type': 'text/csv; charset=utf-8'})


def test_preview_is_read_only_and_import_preserves_fields_and_skips_replay(client):
    owner,pid,path = setup(client)
    with client.sessions() as db: before = db.scalar(select(func.count()).select_from(ActivityLog))
    result = preview(client,path,owner)
    assert result.status_code == 200
    value = result.json()
    assert len(value['rows']) == 2 and value['rows'][1]['priority'] == 'medium' and value['errors'] == []
    assert client.get('/api/tasks',headers=owner).json() == []
    with client.sessions() as db: assert db.scalar(select(func.count()).select_from(ActivityLog)) == before
    selection = {'preview_token':value['preview_token'], 'row_numbers':[2]}
    result = client.post(path+'/import',json=selection,headers=owner)
    assert result.status_code == 200 and result.json()['imported_count'] == 1
    task = client.get('/api/tasks',headers=owner).json()[0]
    assert task['title'] == 'Review release' and task['description'] == 'Check the criteria'
    assert task['priority'] == 'high' and task['status'] == 'todo' and task['project_id'] == pid
    assert client.post(path+'/import',json=selection,headers=owner).json()['skipped_row_numbers'] == [2]
    again = preview(client,path,owner).json()
    assert again['rows'][0]['duplicate_reason'] and again['rows'][1]['duplicate_reason'] is None
    with client.sessions() as db:
        details = json.loads(db.scalar(select(ActivityLog.details).where(ActivityLog.action == 'File task imported')))
        assert details['project_id'] == pid and details['task_id'] == task['id'] and 'description' not in details


def test_deleted_or_edited_imports_are_not_silently_recreated(client):
    owner,pid,path = setup(client)
    value = preview(client,path,owner).json()
    selection = {'preview_token':value['preview_token'], 'row_numbers':[2]}
    task_id = client.post(path+'/import',json=selection,headers=owner).json()['created_task_ids'][0]
    client.patch(f'/api/tasks/{task_id}',json={'title':'Edited title'},headers=owner)
    assert client.post(path+'/import',json=selection,headers=owner).json()['imported_count'] == 0
    client.delete(f'/api/tasks/{task_id}',headers=owner)
    assert client.post(path+'/import',json=selection,headers=owner).json()['imported_count'] == 0


def test_repeated_rows_and_identical_manual_tasks_are_detected(client):
    owner,pid,path = setup(client)
    client.post('/api/tasks',json={'title':'Existing','project_id':pid},headers=owner)
    content = b'title\nExisting\nNew task\nNew task\n'
    value = preview(client,path,owner,content).json()
    assert value['rows'][0]['duplicate_reason'] and value['rows'][1]['duplicate_reason'] is None and value['rows'][2]['duplicate_reason']
    result = client.post(path+'/import',json={'preview_token':value['preview_token'], 'row_numbers':[2,3,4,3]},headers=owner).json()
    assert result['imported_count'] == 1 and result['skipped_row_numbers'] == [2,4]


def test_invalid_rows_are_explained_and_cannot_be_imported(client):
    owner,pid,path = setup(client)
    content = b'title,description,priority\n,Missing title,high\nWrong priority,,urgent\nBad columns\nValid title,Details,low\n'
    value = preview(client,path,owner,content).json()
    assert len(value['errors']) == 3 and [row['row_number'] for row in value['rows']] == [5]
    assert client.post(path+'/import',json={'preview_token':value['preview_token'], 'row_numbers':[2]},headers=owner).status_code == 422
    assert client.get('/api/tasks',headers=owner).json() == []


@pytest.mark.parametrize('content', [b'',b'other\nTask\n',b'title,title\nA,B\n',b'title,assigned_to\nTask,999\n',b'title\n"unterminated',b'title\n\xff',b'title\nBinary\x00'])
def test_malformed_or_unexpected_files_fail_without_creating_tasks(client,content):
    owner,pid,path = setup(client)
    assert preview(client,path,owner,content).status_code in (413,422)
    assert client.get('/api/tasks',headers=owner).json() == []


def test_upload_size_row_count_and_content_type_limits(client):
    owner,pid,path = setup(client)
    assert preview(client,path,owner,b'title\n'+b'x'*(files.MAX_BYTES+1)).status_code == 413
    assert preview(client,path,owner,b'title\n'+b'Task\n'*101).status_code == 422
    assert client.post(path+'/preview',content=CSV,headers={**owner,'Content-Type':'application/octet-stream'}).status_code == 415
    value = preview(client,path,owner,b'title\n'+b'Task\n'*30).json()
    assert client.post(path+'/import',json={'preview_token':value['preview_token'], 'row_numbers':list(range(2,28))},headers=owner).status_code == 422


def test_utf8_bom_quoted_commas_and_multiline_fields_are_preserved(client):
    owner,pid,path = setup(client)
    content = '\ufefftitle,description,priority\r\n"Review, export","Line one\r\nLine two — café",HIGH\r\n'
    value = preview(client,path,owner,content.encode()).json()
    row = value['rows'][0]
    assert row['title'] == 'Review, export' and row['description'] == 'Line one\nLine two — café' and row['priority'] == 'high'
    assert client.post(path+'/import',json={'preview_token':value['preview_token'], 'row_numbers':[2]},headers=owner).status_code == 200


def test_valid_unicode_file_preview_token_can_be_imported(client):
    owner,pid,path = setup(client)
    content = 'title,description\n'+''.join(f'Task {i},'+('é'*4000)+'\n' for i in range(30))
    assert len(content.encode()) < files.MAX_BYTES
    value = preview(client,path,owner,content.encode()).json()
    assert client.post(path+'/import',json={'preview_token':value['preview_token'], 'row_numbers':[2]},headers=owner).status_code == 200


def test_owner_only_preview_and_import_and_no_nonmember_disclosure(client):
    owner,pid,path = setup(client)
    value = preview(client,path,owner).json()
    payload = {'preview_token':value['preview_token'], 'row_numbers':[2]}
    register(client,email='editor@example.com')
    editor = {'Authorization':'Bearer '+login(client,username='editor@example.com').json()['access_token']}
    assert preview(client,path,editor).status_code == 404
    client.post(f'/api/projects/{pid}/members',json={'email':'editor@example.com','role':'editor'},headers=owner)
    assert preview(client,path,editor).status_code == 403
    assert client.post(path+'/import',json=payload,headers=editor).status_code == 403
    client.put(f'/api/projects/{pid}/members/2',json={'role':'viewer'},headers=owner)
    assert preview(client,path,editor).status_code == 403
    assert client.post(path+'/preview',content=CSV,headers={'Content-Type':'text/csv'}).status_code == 401
    assert client.post(path+'/import',json=payload).status_code == 401


def test_preview_binding_tampering_expiration_and_cross_workflow_tokens(client):
    owner,pid,path = setup(client)
    value = preview(client,path,owner).json()
    other = client.post('/api/projects',json={'name':'Other'},headers=owner).json()['id']
    payload = {'preview_token':value['preview_token'], 'row_numbers':[2]}
    assert client.post(f'/api/projects/{other}/files/import',json=payload,headers=owner).status_code == 422
    assert client.post(path+'/import',json={**payload,'preview_token':value['preview_token'][:-6]+'broken'},headers=owner).status_code == 422
    claims = jwt.decode(value['preview_token'],files.SECRET_KEY,algorithms=[files.ALGORITHM],audience=str(pid),issuer=files.PREVIEW_ISSUER)
    claims['exp'] = datetime.now(timezone.utc)-timedelta(seconds=1)
    expired = jwt.encode(claims,files.SECRET_KEY,algorithm=files.ALGORITHM)
    assert client.post(path+'/import',json={**payload,'preview_token':expired},headers=owner).status_code == 422
    assert client.post(f'/api/projects/{pid}/github/import',json={'preview_token':value['preview_token'],'issue_numbers':[2]},headers=owner).status_code == 422
    assert client.get('/api/tasks',headers=owner).json() == []


def test_template_is_downloadable_and_parses(client):
    response = client.get('/api/task-import-template.csv')
    assert response.status_code == 200 and 'attachment' in response.headers['content-disposition']
    rows, errors = files.parse_csv(response.content)
    assert len(rows) == 2 and not errors


def test_custom_columns_are_explicit_read_only_and_preserve_deduplication(client):
    owner,pid,path=setup(client)
    content=b'Summary,Notes,Importance,Assignee,State\nMapped task,Check release,HIGH,999,done\n'
    with client.sessions() as db: before=db.scalar(select(func.count()).select_from(ActivityLog))
    columns=client.post(path+'/columns',content=content,headers={**owner,'Content-Type':'text/csv'})
    assert columns.status_code==200
    assert columns.json()['columns'][0]=={'index':0,'label':'Summary'}
    assert 'Mapped task' not in columns.text
    assert preview(client,path,owner,content).status_code==422
    mapped=client.post(path+'/preview',content=content,headers={**owner,'Content-Type':'text/csv','X-CSV-Mapping':json.dumps({'title':0,'description':1,'priority':2})})
    assert mapped.status_code==200
    value=mapped.json();row=value['rows'][0]
    assert row['title']=='Mapped task' and row['description']=='Check release' and row['priority']=='high'
    assert 'assigned_to' not in row and 'status' not in row
    assert client.get('/api/tasks',headers=owner).json()==[]
    with client.sessions() as db: assert db.scalar(select(func.count()).select_from(ActivityLog))==before
    result=client.post(path+'/import',json={'preview_token':value['preview_token'],'row_numbers':[2]},headers=owner)
    assert result.json()['imported_count']==1
    task=client.get('/api/tasks',headers=owner).json()[0]
    assert task['assigned_to']==1 and task['status']=='todo'
    canonical=preview(client,path,owner,b'title,description,priority\nMapped task,Check release,high\n').json()
    assert canonical['rows'][0]['duplicate_reason']


@pytest.mark.parametrize('mapping',[{},None,[],{'title':True},{'title':-1},{'title':5},{'title':'0'},{'title':0,'description':0},{'title':0,'status':1},{'title':0,'assigned_to':1}])
def test_invalid_mappings_cannot_change_tasks(client,mapping):
    owner,pid,path=setup(client)
    result=client.post(path+'/preview',content=b'Summary,Other\nTask,Detail\n',headers={**owner,'Content-Type':'text/csv','X-CSV-Mapping':json.dumps(mapping)})
    assert result.status_code==422
    assert client.get('/api/tasks',headers=owner).json()==[]


def test_mapping_optional_columns_defaults_duplicate_headings_and_validation(client):
    owner,pid,path=setup(client)
    content=b'Name,Name,Extra\nIgnored,Chosen,done\n'
    value=client.post(path+'/preview',content=content,headers={**owner,'Content-Type':'text/csv','X-CSV-Mapping':'{"title":1}'}).json()
    assert value['rows'][0]['title']=='Chosen' and value['rows'][0]['description']=='' and value['rows'][0]['priority']=='medium'
    invalid=client.post(path+'/preview',content=b'Summary,Importance\nTask,urgent\n',headers={**owner,'Content-Type':'text/csv','X-CSV-Mapping':'{"title":0,"priority":1}'}).json()
    assert invalid['rows']==[] and 'Priority' in invalid['errors'][0]['message']
    for heading in [','.join(['Column']*41),'x'*101,'Bad\x01heading']:
        result=client.post(path+'/columns',content=(heading+'\nTask\n').encode(),headers={**owner,'Content-Type':'text/csv'})
        assert result.status_code==422
    for mapping in ['{broken','x'*1001]:
        assert client.post(path+'/preview',content=CSV,headers={**owner,'Content-Type':'text/csv','X-CSV-Mapping':mapping}).status_code==422


def test_column_inspection_requires_owner_and_bounded_csv(client):
    owner,pid,path=setup(client)
    assert client.post(path+'/columns',content=CSV,headers={'Content-Type':'text/csv'}).status_code==401
    register(client,email='columns@example.com')
    outsider={'Authorization':'Bearer '+login(client,username='columns@example.com').json()['access_token']}
    assert client.post(path+'/columns',content=CSV,headers={**outsider,'Content-Type':'text/csv'}).status_code==404
    client.post(f'/api/projects/{pid}/members',json={'email':'columns@example.com','role':'editor'},headers=owner)
    assert client.post(path+'/columns',content=CSV,headers={**outsider,'Content-Type':'text/csv'}).status_code==403
    assert client.post(path+'/columns',content=CSV,headers={**owner,'Content-Type':'message/rfc822'}).status_code==415
    assert client.post(path+'/columns',content=b'x'*(files.MAX_BYTES+1),headers={**owner,'Content-Type':'text/csv'}).status_code==413
    assert client.post(path+'/columns',content=b'title\n\xff',headers={**owner,'Content-Type':'text/csv'}).status_code==422
    assert client.post(path+'/preview',content=b'Subject: Task\n\nBody',headers={**owner,'Content-Type':'message/rfc822','X-CSV-Mapping':'{"title":0}'}).status_code==422
