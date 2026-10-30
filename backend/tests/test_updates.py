from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,func
from test_auth import client,register,login
from test_tracker import headers
from models import InboxNotice,TaskReminder,ProjectProgress,NotificationSettings,User,Task


def setup(client):
    owner=headers(client);project=client.post('/api/projects',headers=owner,json={'name':'Progress project'}).json()
    task=client.post('/api/tasks',headers=owner,json={'title':'Release task','project_id':project['id']}).json()
    return owner,project['id'],task['id']


def due(client,user_id,task_id):
    with client.sessions() as db:db.get(TaskReminder,(user_id,task_id)).remind_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()


def test_reminder_is_persistent_private_and_delivered_once_when_checked(client):
    owner,pid,tid=setup(client)
    value=client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':1})
    assert value.status_code==200 and value.json()['task_id']==tid
    assert client.get('/api/reminders',headers=owner).json()[0]['title']=='Release task'
    assert client.get('/api/updates/summary',headers=owner).json()['unread_count']==0
    due(client,1,tid)
    assert client.get('/api/updates/summary',headers=owner).json()['unread_count']==1
    page=client.get('/api/updates',headers=owner).json();assert len(page['items'])==1
    item=page['items'][0];assert item['category']=='reminder' and item['task_id']==tid and item['project_name']=='Progress project'
    assert client.get('/api/reminders',headers=owner).json()==[]
    assert client.get('/api/updates/summary',headers=owner).json()['unread_count']==1
    with client.sessions() as db:assert db.get(TaskReminder,(1,tid)).delivered and db.scalar(select(func.count()).select_from(InboxNotice))==1
    assert client.get(f'/api/updates/tasks/{tid}',headers=owner).json()['title']=='Release task'


def test_reminder_reschedule_cancel_and_completed_suppression(client):
    owner,pid,tid=setup(client)
    first=client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':1}).json()
    second=client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':60}).json()
    assert second['remind_at']>first['remind_at']
    assert client.delete(f'/api/reminders/{tid}',headers=owner).status_code==204
    assert client.get('/api/reminders',headers=owner).json()==[]
    client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':1});due(client,1,tid)
    client.patch(f'/api/tasks/{tid}',headers=owner,json={'status':'done'})
    assert client.get('/api/updates?category=reminder',headers=owner).json()['items']==[]
    assert client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':1}).status_code==409


def test_progress_baseline_changes_and_muting_are_real_and_deduplicated(client):
    owner,pid,tid=setup(client)
    assert client.get('/api/updates',headers=owner).json()['items']==[]
    with client.sessions() as db:assert db.get(ProjectProgress,(1,pid)).total==1
    client.patch(f'/api/tasks/{tid}',headers=owner,json={'status':'done'})
    page=client.get('/api/updates?category=progress',headers=owner).json()
    assert len(page['items'])==1 and '1 of 1' in page['items'][0]['message'] and '100%' in page['items'][0]['message']
    assert client.get('/api/updates',headers=owner).json()['unread_count']==1
    client.patch(f'/api/tasks/{tid}',headers=owner,json={'status':'todo'});client.get('/api/updates',headers=owner)
    client.patch(f'/api/tasks/{tid}',headers=owner,json={'status':'done'})
    assert len(client.get('/api/updates?category=progress',headers=owner).json()['items'])==2
    assert client.patch('/api/update-preferences',headers=owner,json={'enabled':False}).json()['progress_enabled'] is False
    client.post('/api/tasks',headers=owner,json={'title':'New task','project_id':pid});client.get('/api/updates',headers=owner)
    client.patch('/api/update-preferences',headers=owner,json={'enabled':True})
    assert len(client.get('/api/updates?category=progress',headers=owner).json()['items'])==2


def test_read_unread_and_mark_all_are_user_and_membership_scoped(client):
    owner,pid,tid=setup(client)
    register(client,email='second@example.com');second={'Authorization':'Bearer '+login(client,username='second@example.com').json()['access_token']}
    client.post(f'/api/projects/{pid}/members',headers=owner,json={'email':'second@example.com','role':'viewer'})
    with client.sessions() as db:
        db.add_all([InboxNotice(user_id=1,project_id=pid,task_id=tid,event_key='a'*64,message='Task assigned: Release task'),InboxNotice(user_id=2,project_id=pid,task_id=tid,event_key='b'*64,message='Task assigned: Release task')]);db.commit()
    item=client.get('/api/updates?unread=true&category=assignment',headers=owner).json()['items'][0]
    assert client.patch(f"/api/updates/{item['id']}",headers=second,json={'read':True}).status_code==404
    assert client.patch(f"/api/updates/{item['id']}",headers=owner,json={'read':True}).json()['read'] is True
    assert client.get('/api/updates?unread=true',headers=owner).json()['items']==[]
    client.patch(f"/api/updates/{item['id']}",headers=owner,json={'read':False})
    assert client.get('/api/updates/summary',headers=owner).json()['unread_count']==1
    assert client.post('/api/updates/read-all',headers=owner).json()['unread_count']==0
    assert client.get('/api/updates/summary',headers=second).json()['unread_count']==1


def test_viewer_can_set_only_personal_reminder_and_revocation_hides_content(client):
    owner,pid,tid=setup(client)
    register(client,email='viewer@example.com');viewer={'Authorization':'Bearer '+login(client,username='viewer@example.com').json()['access_token']}
    assert client.get(f'/api/updates/tasks/{tid}',headers=viewer).status_code==404
    assert client.post(f'/api/reminders/{tid}',headers=viewer,json={'minutes':1}).status_code==404
    client.post(f'/api/projects/{pid}/members',headers=owner,json={'email':'viewer@example.com','role':'viewer'})
    assert client.get(f'/api/updates/tasks/{tid}',headers=viewer).json()['can_edit'] is False
    assert client.post(f'/api/reminders/{tid}',headers=viewer,json={'minutes':1}).status_code==200
    due(client,2,tid);notice=client.get('/api/updates',headers=viewer).json()['items'][0]
    assert client.delete(f'/api/projects/{pid}/members/2',headers=owner).status_code==204
    assert client.get('/api/updates',headers=viewer).json()['items']==[]
    assert client.get('/api/updates/summary',headers=viewer).json()['unread_count']==0
    assert client.patch(f"/api/updates/{notice['id']}",headers=viewer,json={'read':True}).status_code==404
    assert client.get(f'/api/updates/tasks/{tid}',headers=viewer).status_code==404


def test_deleted_and_moved_tasks_do_not_expose_task_actions_or_trigger_old_reminders(client):
    owner,pid,tid=setup(client)
    client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':1})
    with client.sessions() as db:db.add(InboxNotice(project_id=pid,user_id=1,task_id=tid,event_key='d'*64,message='Task assigned: Release task'));db.commit()
    assert client.delete(f'/api/tasks/{tid}',headers=owner).status_code==204
    assert client.get('/api/updates',headers=owner).json()['items'][0]['task_id'] is None
    assert client.get('/api/reminders',headers=owner).json()==[]
    assert client.delete(f'/api/projects/{pid}',headers=owner).status_code==204
    assert client.get('/api/updates',headers=owner).json()['items']==[]


@pytest.mark.parametrize('minutes',[0,2,-1,1441,'tomorrow'])
def test_invalid_reminder_inputs_do_not_write(client,minutes):
    owner,pid,tid=setup(client)
    assert client.post(f'/api/reminders/{tid}',headers=owner,json={'minutes':minutes}).status_code==422
    assert client.get('/api/reminders',headers=owner).json()==[]


def test_update_pagination_filters_and_no_external_delivery(client,monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',lambda *args,**kwargs:pytest.fail('Updates must not send external messages'))
    owner,pid,tid=setup(client)
    with client.sessions() as db:
        for i in range(28):db.add(InboxNotice(user_id=1,project_id=pid,event_key=str(i).zfill(64),message='Task assigned: Fixture'))
        db.commit()
    first=client.get('/api/updates',headers=owner).json();assert len(first['items'])==25 and first['next_cursor'] and first['unread_count']==28
    second=client.get('/api/updates?cursor='+str(first['next_cursor']),headers=owner).json();assert len(second['items'])==3
    assert client.get('/api/updates?category=reminder',headers=owner).json()['items']==[]
    assert client.get('/api/updates').status_code==401
    assert client.get('/api/reminders').status_code==401


def test_updates_migration_is_additive_and_repeatable(client):
    from migrate_updates import upgrade
    owner,pid,tid=setup(client)
    with client.sessions() as db:
        original=db.get(User,1).password_hash;connection=db.connection()
        assert upgrade(connection) and not upgrade(connection)
        assert db.get(User,1).password_hash==original and db.get(Task,tid).title=='Release task'
        for table in (TaskReminder,ProjectProgress,NotificationSettings):assert db.scalar(select(func.count()).select_from(table))==0
        db.commit()
