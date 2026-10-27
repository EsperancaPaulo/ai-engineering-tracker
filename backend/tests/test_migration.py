import pytest
from sqlalchemy import create_engine, insert, select, func
from database import Base
from models import AppMigration, ProjectMember, User, Project, Task, ActivityLog
from migrate import upgrade


def legacy_database(user_count=1):
    engine=create_engine('sqlite://')
    for model in [User,Project,Task,ActivityLog]:
        model.__table__.create(engine)
    with engine.begin() as connection:
        for uid in range(1,user_count+1):
            connection.execute(insert(User).values(id=uid,name=f'Person {uid}',email=f'p{uid}@example.com',password_hash='fixture-hash'))
        if user_count:
            connection.execute(insert(Project).values(id=1,name='Existing',description='Keep this'))
            connection.execute(insert(Task).values(id=1,title='Keep task',project_id=1,assigned_to=1))
            connection.execute(insert(ActivityLog).values(id=1,user_id=1,action='Original history',details='Keep history'))
    return engine


def test_single_user_backfill_preserves_data_and_is_idempotent():
    engine=legacy_database()
    with engine.begin() as connection:
        assert upgrade(connection) is True
        assert upgrade(connection) is False
        assert connection.scalar(select(ProjectMember.role))=='owner'
        assert connection.scalar(select(Task.title))=='Keep task'
        assert connection.scalar(select(Project.description))=='Keep this'
        assert connection.scalar(select(User.password_hash))=='fixture-hash'
        assert connection.scalar(select(ActivityLog.details))=='Keep history'
        assert connection.scalar(select(func.count()).select_from(AppMigration))==1


def test_multiple_users_require_explicit_owner():
    engine=legacy_database(2)
    with engine.begin() as connection:
        with pytest.raises(ValueError): upgrade(connection)
    with engine.begin() as connection:
        assert upgrade(connection,legacy_owner_id=2) is True
        assert dict(connection.execute(select(ProjectMember.user_id,ProjectMember.role)).all())=={1:'editor',2:'owner'}


def test_empty_database_migration():
    engine=legacy_database(0)
    with engine.begin() as connection:
        assert upgrade(connection) is True
        assert list(connection.scalars(select(ProjectMember.user_id)))==[]


def test_automation_migration_adds_empty_storage_without_rewriting_records():
    from models import AutomationRule
    from migrate_automation import upgrade as upgrade_automation
    engine=legacy_database()
    with engine.begin() as connection:
        upgrade(connection)
        before={model.__tablename__:connection.execute(select(model.__table__)).all() for model in [User,Project,Task,ActivityLog,ProjectMember]}
        assert upgrade_automation(connection) is True
        assert upgrade_automation(connection) is False
        assert connection.scalar(select(func.count()).select_from(AutomationRule))==0
        for model in [User,Project,Task,ActivityLog,ProjectMember]:assert connection.execute(select(model.__table__)).all()==before[model.__tablename__]


def test_workflow_migration_preserves_original_records_and_starts_empty():
    from models import InboxNotice,SlackDelivery,RevokedSession,UserSecurity,EmailGrant
    from migrate_automation import upgrade as automation_upgrade
    from migrate_workflows import upgrade as workflow_upgrade
    engine=legacy_database()
    with engine.begin() as connection:
        upgrade(connection);automation_upgrade(connection)
        before=connection.execute(select(User.__table__)).all()
        assert workflow_upgrade(connection) is True and workflow_upgrade(connection) is False
        assert connection.execute(select(User.__table__)).all()==before
        for model in (InboxNotice,SlackDelivery,RevokedSession,UserSecurity,EmailGrant):assert connection.scalar(select(func.count()).select_from(model))==0
