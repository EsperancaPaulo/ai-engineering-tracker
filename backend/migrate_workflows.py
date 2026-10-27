"""Add notification, delivery and logout-revocation storage without rewriting existing data."""
from sqlalchemy import insert,select,text
from models import AppMigration,InboxNotice,SlackDelivery,RevokedSession,UserSecurity,EmailGrant
VERSION='003_non_ai_workflows'

def upgrade(connection):
    if connection.dialect.name=='postgresql':connection.execute(text('SELECT pg_advisory_xact_lock(830017001)'))
    AppMigration.__table__.create(connection,checkfirst=True)
    if connection.scalar(select(AppMigration.version).where(AppMigration.version==VERSION)):return False
    for model in (InboxNotice,SlackDelivery,RevokedSession,UserSecurity,EmailGrant):model.__table__.create(connection,checkfirst=True)
    connection.execute(insert(AppMigration).values(version=VERSION));return True

if __name__=='__main__':
    from database import engine
    with engine.begin() as connection:changed=upgrade(connection)
    print('Workflow storage added.' if changed else 'Workflow migration already applied.')
